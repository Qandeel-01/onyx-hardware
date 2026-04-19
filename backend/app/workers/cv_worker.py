"""Background CV worker: YOLO inference and frame annotation."""

import asyncio
import logging
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.session import SessionVideo
from app.models.events import VideoFrameEvent

logger = logging.getLogger(__name__)


class CVWorker:
    """Async worker for video processing and YOLO inference."""

    def __init__(self):
        """Initialize CV worker."""
        self.model: YOLO | None = None

    async def load_model(self) -> YOLO:
        """Load YOLO model (lazy load).

        Returns:
            YOLO model instance
        """
        if self.model is None:
            logger.info(f"Loading YOLO model from {settings.yolo_model_path}")
            self.model = YOLO(settings.yolo_model_path)
        return self.model

    async def process_video(
        self,
        session_id: int,
        video_id: int,
        video_path: str,
        db: AsyncSession,
    ) -> int:
        """Process video file: probe, inference, frame events.

        Args:
            session_id: Session ID
            video_id: SessionVideo ID
            video_path: Path to video file
            db: Database session

        Returns:
            Number of frame events created
        """
        logger.info(f"Processing video {video_path} for session {session_id}")

        # Probe video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Cannot open video: {video_path}")
            return 0

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info(f"Video: {fps} fps, {frame_count} frames")

        # Update SessionVideo metadata
        video_stmt = select(SessionVideo).where(SessionVideo.id == video_id)
        video_record = (await db.execute(video_stmt)).scalar_one_or_none()
        if video_record:
            video_record.fps = fps
            video_record.frame_count = frame_count
            video_record.duration_seconds = frame_count / fps if fps > 0 else 0
            video_record.encoding_status = "processing"

        await db.commit()

        # Load model
        model = await self.load_model()

        frame_count_processed = 0
        frame_events_created = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1

                # Skip frames based on cv_frame_skip
                if frame_idx % settings.cv_frame_skip != 0:
                    continue

                # Run YOLO inference
                results = model(frame, verbose=False)

                for result in results:
                    # Extract pose keypoints
                    if result.keypoints is not None:
                        kpts = result.keypoints.xy.cpu().numpy()
                        poses = result.keypoints.conf.cpu().numpy()

                        for person_idx, (kpt, conf) in enumerate(zip(kpts, poses)):
                            # Simple court projection: map image coords to court coords
                            # (Simplified; real implementation would use homography)
                            img_h, img_w = frame.shape[:2]
                            court_x_m = (kpt[:, 0].mean() / img_w) * 10.0  # Normalize to 10m court width
                            court_y_m = (kpt[:, 1].mean() / img_h) * 20.0  # Normalize to 20m court length

                            pose_quality = float(conf.mean())

                            # Create VideoFrameEvent
                            frame_event = VideoFrameEvent(
                                session_id=session_id,
                                video_id=video_id,
                                frame_index=frame_idx,
                                frame_utc_ms=None,  # Will be set during fusion
                                court_x_m=court_x_m,
                                court_y_m=court_y_m,
                                pose_keypoints=kpt.tolist(),
                                pose_quality=pose_quality,
                                person_count=1,
                            )
                            db.add(frame_event)
                            frame_events_created += 1

                frame_count_processed += 1
                if frame_count_processed % 100 == 0:
                    logger.info(f"Processed {frame_count_processed} frames")

        finally:
            cap.release()

        await db.commit()

        # Update status
        if video_record:
            video_record.encoding_status = "complete"
            await db.commit()

        logger.info(
            f"Video processing complete: {frame_count_processed} frames, "
            f"{frame_events_created} frame events created"
        )

        return frame_events_created


# Global worker instance
_cv_worker: CVWorker | None = None


async def get_cv_worker() -> CVWorker:
    """Get or create global CV worker."""
    global _cv_worker
    if _cv_worker is None:
        _cv_worker = CVWorker()
    return _cv_worker
