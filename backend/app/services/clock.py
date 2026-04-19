"""SNTP-based clock synchronization and frame mapping."""

import logging
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class ClockSyncManager:
    """Manages SNTP clock synchronization and frame index mapping."""

    def __init__(self):
        """Initialize clock sync manager."""
        self.samples: list[dict] = []
        self.device_offset_ms: Optional[float] = None
        self.rtt_ms: Optional[float] = None
        self.quality: str = "unknown"

    def add_sample(
        self,
        t1_device_ms: float,
        t2_server_utc_ms: float,
        t3_server_utc_ms: float,
        t4_device_ms: float,
    ) -> None:
        """Add SNTP timestamp sample.

        Args:
            t1_device_ms: Device timestamp when sending request
            t2_server_utc_ms: Server UTC timestamp when receiving request
            t3_server_utc_ms: Server UTC timestamp when sending response
            t4_device_ms: Device timestamp when receiving response

        SNTP math (RFC 5905):
            offset = ((t2 - t1) + (t3 - t4)) / 2
            delay = (t4 - t1) - (t3 - t2)
        """
        offset = ((t2_server_utc_ms - t1_device_ms) + (t3_server_utc_ms - t4_device_ms)) / 2
        delay = (t4_device_ms - t1_device_ms) - (t3_server_utc_ms - t2_server_utc_ms)

        self.samples.append({
            "t1": t1_device_ms,
            "t2": t2_server_utc_ms,
            "t3": t3_server_utc_ms,
            "t4": t4_device_ms,
            "offset": offset,
            "delay": delay,
        })

        logger.info(f"Clock sync sample: offset={offset:.2f}ms, delay={delay:.2f}ms")

    def finalize(self) -> Tuple[float, str]:
        """Finalize sync by selecting best sample (min RTT).

        Returns:
            (device_offset_ms, quality_indicator)
        """
        if not self.samples:
            logger.warning("No clock sync samples available")
            return 0.0, "no_samples"

        # Select sample with minimum RTT
        best_sample = min(self.samples, key=lambda s: abs(s["delay"]))
        self.device_offset_ms = best_sample["offset"]
        self.rtt_ms = abs(best_sample["delay"])

        # Quality assessment
        if self.rtt_ms < 50:
            self.quality = "excellent"
        elif self.rtt_ms < 100:
            self.quality = "good"
        elif self.rtt_ms < 200:
            self.quality = "fair"
        else:
            self.quality = "poor"

        logger.info(
            f"Clock sync finalized: offset={self.device_offset_ms:.2f}ms, "
            f"rtt={self.rtt_ms:.2f}ms, quality={self.quality}"
        )
        return self.device_offset_ms, self.quality

    def device_ts_to_utc_ms(self, device_ts_ms: float) -> float:
        """Convert device timestamp to UTC.

        Args:
            device_ts_ms: Device local timestamp (milliseconds)

        Returns:
            UTC timestamp (milliseconds)
        """
        if self.device_offset_ms is None:
            logger.warning("Clock sync not finalized; using device timestamp as-is")
            return device_ts_ms
        return device_ts_ms + self.device_offset_ms

    def frame_index_from_utc(
        self,
        utc_ts_ms: float,
        video_start_utc_ms: float,
        fps: float,
        frame_rate_type: str = "cfr",
    ) -> Tuple[int, float]:
        """Map UTC timestamp to video frame index.

        Args:
            utc_ts_ms: UTC timestamp (milliseconds)
            video_start_utc_ms: UTC timestamp of video start
            fps: Frames per second
            frame_rate_type: 'cfr' (constant) or 'vfr' (variable)

        Returns:
            (frame_index, fractional_frame)
        """
        if utc_ts_ms < video_start_utc_ms:
            logger.warning(
                f"Timestamp {utc_ts_ms} is before video start {video_start_utc_ms}"
            )
            return 0, 0.0

        elapsed_ms = utc_ts_ms - video_start_utc_ms
        elapsed_seconds = elapsed_ms / 1000.0
        frame_float = elapsed_seconds * fps
        frame_index = int(frame_float)
        fractional = frame_float - frame_index

        return frame_index, fractional

    def utc_from_frame_index(
        self,
        frame_index: int,
        video_start_utc_ms: float,
        fps: float,
    ) -> float:
        """Reverse mapping: frame index → UTC timestamp.

        Args:
            frame_index: Video frame number (0-indexed)
            video_start_utc_ms: UTC timestamp of video start
            fps: Frames per second

        Returns:
            UTC timestamp (milliseconds)
        """
        elapsed_seconds = frame_index / fps
        return video_start_utc_ms + (elapsed_seconds * 1000.0)
