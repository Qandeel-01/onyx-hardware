"""LED flash detection from video frames using OpenCV."""

import logging
from typing import List, Tuple, Optional

import cv2
import numpy as np
from scipy import signal

logger = logging.getLogger(__name__)


class FlashDetector:
    """Detects LED flash pulses in video frames."""

    def __init__(
        self,
        prominence: float = 15.0,
        min_distance_frames: int = 5,
    ):
        """Initialize flash detector.

        Args:
            prominence: Peak prominence threshold (0-255 brightness units)
            min_distance_frames: Minimum frames between peaks
        """
        self.prominence = prominence
        self.min_distance_frames = min_distance_frames

    def detect_flashes(self, video_path: str) -> List[Tuple[int, float]]:
        """Detect LED flashes in video.

        Args:
            video_path: Path to video file

        Returns:
            List of (frame_index, brightness_peak) tuples
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Cannot open video: {video_path}")
            return []

        brightness_series = []
        frame_count = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Convert to grayscale and compute mean brightness
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                mean_brightness = gray.mean()
                brightness_series.append(mean_brightness)
                frame_count += 1

        finally:
            cap.release()

        if frame_count == 0:
            logger.warning("No frames read from video")
            return []

        brightness_array = np.array(brightness_series, dtype=np.float32)

        # Detect peaks using scipy.signal.find_peaks
        peaks, properties = signal.find_peaks(
            brightness_array,
            prominence=self.prominence,
            distance=self.min_distance_frames,
        )

        flashes = [(int(idx), float(brightness_array[idx])) for idx in peaks]
        logger.info(f"Detected {len(flashes)} flashes in {frame_count} frames")

        return flashes

    def compute_residual_offset(
        self,
        detected_flash_frames: List[int],
        device_timestamps_ms: List[float],
        fps: float,
        video_start_utc_ms: float,
    ) -> Tuple[float, float]:
        """Compute residual clock offset from detected flashes vs device timestamps.

        Args:
            detected_flash_frames: Frame indices of detected LED flashes
            device_timestamps_ms: Device timestamps corresponding to LED pulses
            fps: Video frames per second
            video_start_utc_ms: UTC timestamp of video start

        Returns:
            (residual_offset_ms, median_absolute_deviation_ms)
        """
        if len(detected_flash_frames) != len(device_timestamps_ms):
            logger.warning(
                f"Mismatch: detected {len(detected_flash_frames)} flashes "
                f"but got {len(device_timestamps_ms)} device timestamps"
            )

        offsets = []
        for frame_idx, device_ts_ms in zip(detected_flash_frames, device_timestamps_ms):
            # Convert frame index to UTC
            frame_utc_ms = video_start_utc_ms + (frame_idx / fps) * 1000.0
            offset = frame_utc_ms - device_ts_ms
            offsets.append(offset)
            logger.debug(f"Flash {frame_idx}: device={device_ts_ms:.1f}, video_utc={frame_utc_ms:.1f}, offset={offset:.1f}ms")

        offsets_array = np.array(offsets, dtype=np.float32)
        residual_offset = float(np.median(offsets_array))

        # Median absolute deviation
        mad = float(np.median(np.abs(offsets_array - residual_offset)))

        logger.info(f"Residual offset: {residual_offset:.2f}ms ± {mad:.2f}ms")

        return residual_offset, mad
