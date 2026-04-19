"""Fusion service: maps sensor events to fused shots using clock sync and CV frame data."""

import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.session import Session, SessionClockSync
from app.models.events import SensorEvent, VideoFrameEvent, FusedShot
from app.services.clock import ClockSyncManager

logger = logging.getLogger(__name__)


class FusionEngine:
    """Fuses sensor events with video frame events."""

    FUSION_WINDOW_MS = 150  # ±150ms window for matching frames

    async def fuse_session(
        self,
        session_id: int,
        db: AsyncSession,
    ) -> int:
        """Fuse all sensor events in a session with video frame events.

        Args:
            session_id: Session ID to fuse
            db: Database session

        Returns:
            Number of fused shots created
        """
        # Fetch session with clock syncs
        session_stmt = select(Session).where(Session.id == session_id)
        session = (await db.execute(session_stmt)).scalar_one_or_none()
        if not session:
            logger.warning(f"Session {session_id} not found")
            return 0

        # Rebuild clock sync manager from session's clock syncs
        clock_mgr = ClockSyncManager()
        syncs_stmt = select(SessionClockSync).where(
            SessionClockSync.session_id == session_id
        )
        syncs = (await db.execute(syncs_stmt)).scalars().all()

        for sync in syncs:
            clock_mgr.add_sample(
                sync.t1_device_ms,
                sync.t2_server_utc_ms,
                sync.t3_server_utc_ms,
                sync.t4_device_ms,
            )

        clock_mgr.finalize()
        logger.info(f"Rebuilt clock sync for session {session_id}: offset={clock_mgr.device_offset_ms:.2f}ms")

        # Fetch all sensor events for this session
        sensor_stmt = select(SensorEvent).where(SensorEvent.session_id == session_id)
        sensor_events = (await db.execute(sensor_stmt)).scalars().all()
        logger.info(f"Found {len(sensor_events)} sensor events")

        # Fetch all video frame events
        frame_stmt = select(VideoFrameEvent).where(VideoFrameEvent.session_id == session_id)
        frame_events = (await db.execute(frame_stmt)).scalars().all()
        logger.info(f"Found {len(frame_events)} video frame events")

        if not frame_events:
            logger.warning("No video frame events found; creating sensor-only fusions")
            return await self._fuse_sensor_only(session_id, sensor_events, db)

        # For each sensor event, find best matching frame event
        fused_count = 0
        for sensor_event in sensor_events:
            # Skip if already fused
            existing_stmt = select(FusedShot).where(
                FusedShot.sensor_event_id == sensor_event.id
            )
            if await db.execute(existing_stmt):
                continue

            # Convert sensor device timestamp to UTC
            sensor_utc_ms = clock_mgr.device_ts_to_utc_ms(sensor_event.device_ts_ms)

            # Find matching video frame within window
            best_frame = None
            best_distance_ms = float("inf")

            for frame_event in frame_events:
                if frame_event.frame_utc_ms is None:
                    continue

                distance = abs(frame_event.frame_utc_ms - sensor_utc_ms)
                if distance < self.FUSION_WINDOW_MS and distance < best_distance_ms:
                    best_frame = frame_event
                    best_distance_ms = distance

            # Create fused shot
            fusion_confidence = 1.0 if best_distance_ms < 50 else (0.7 if best_distance_ms < self.FUSION_WINDOW_MS else 0.3)

            fused_shot = FusedShot(
                session_id=session_id,
                sensor_event_id=sensor_event.id,
                video_frame_event_id=best_frame.id if best_frame else None,
                shot_type=sensor_event.shot_type,
                court_x_m=best_frame.court_x_m if best_frame else None,
                court_y_m=best_frame.court_y_m if best_frame else None,
                sensor_confidence=sensor_event.confidence,
                vision_confidence=best_frame.pose_quality if best_frame else None,
                fusion_confidence=fusion_confidence,
                fusion_metadata={
                    "distance_ms": best_distance_ms,
                    "clock_offset_ms": clock_mgr.device_offset_ms,
                    "clock_quality": clock_mgr.quality,
                },
            )

            db.add(fused_shot)
            fused_count += 1

            logger.debug(
                f"Fused shot {sensor_event.id}: frame_dist={best_distance_ms:.1f}ms, "
                f"confidence={fusion_confidence:.2f}"
            )

        await db.commit()
        logger.info(f"Fusion complete: {fused_count} shots fused")
        return fused_count

    async def _fuse_sensor_only(
        self,
        session_id: int,
        sensor_events: List[SensorEvent],
        db: AsyncSession,
    ) -> int:
        """Create fusions without video frame data (sensor events only).

        Args:
            session_id: Session ID
            sensor_events: List of sensor events
            db: Database session

        Returns:
            Number of fusions created
        """
        for sensor_event in sensor_events:
            fused_shot = FusedShot(
                session_id=session_id,
                sensor_event_id=sensor_event.id,
                video_frame_event_id=None,
                shot_type=sensor_event.shot_type,
                court_x_m=None,
                court_y_m=None,
                sensor_confidence=sensor_event.confidence,
                vision_confidence=None,
                fusion_confidence=0.3,  # Lower confidence without video
                fusion_metadata={"source": "sensor_only"},
            )
            db.add(fused_shot)

        await db.commit()
        logger.info(f"Created {len(sensor_events)} sensor-only fusions")
        return len(sensor_events)
