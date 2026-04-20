"""InfluxDB time-series backend service"""

import asyncio
import logging
from influxdb_client.client.influxdb_client import InfluxDBClient
from influxdb_client.client.write.point import Point
from influxdb_client.client.write_api import ASYNCHRONOUS, WriteOptions
from app.config import settings
from app.schemas import SensorDataIn

logger = logging.getLogger(__name__)


class InfluxService:
    """Manages InfluxDB connections and writes for sensor data"""
    
    def __init__(self):
        """Initialize InfluxDB client with async write options"""
        self._available = False
        self.client = None
        self.write_api = None
        
        try:
            self.client = InfluxDBClient(
                url=settings.INFLUXDB_URL,
                token=settings.INFLUXDB_TOKEN,
                org=settings.INFLUXDB_ORG,
                timeout=5000  # 5 second timeout
            )
            
            # Configure batch write options (buffer 50 points or flush every 1 second)
            write_options = WriteOptions(
                batch_size=50,
                flush_interval=1000,  # milliseconds
                max_retries=3,
                max_retry_delay=125,
            )
            
            self.write_api = self.client.write_api(
                write_options=write_options
            )
            
            # Test connectivity
            self.client.ping()
            self._available = True
            logger.info("✓ InfluxDB connected")
            
        except Exception as e:
            logger.warning(f"⚠ InfluxDB unavailable: {e}")
            self._available = False
    
    async def write(self, data: SensorDataIn, session_id: str | None) -> None:
        """
        Asynchronously write sensor data to InfluxDB.
        Fire-and-forget: never blocks the response.
        """
        if not self._available or not self.write_api:
            return
        
        try:
            # Build InfluxDB point
            point = Point("mpu6050") \
                .tag("device", data.device_id) \
                .tag("session", session_id or "none") \
                .tag("shot_type", data.shot_type) \
                .field("ax", float(data.ax)) \
                .field("ay", float(data.ay)) \
                .field("az", float(data.az)) \
                .field("gx", float(data.gx)) \
                .field("gy", float(data.gy)) \
                .field("gz", float(data.gz)) \
                .field("confidence", float(data.confidence)) \
                .time(int(data.timestamp * 1e9))  # Convert to nanoseconds
            
            # Run write in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.write_api.write(  # write_api is guaranteed non-None from check above
                    bucket=settings.INFLUXDB_BUCKET,
                    org=settings.INFLUXDB_ORG,
                    record=point
                ) if self.write_api else None
            )
            
        except Exception as e:
            logger.error(f"InfluxDB write failed: {e}")
    
    async def ping(self) -> bool:
        """Health check for InfluxDB"""
        if not self.client:
            return False
        try:
            self.client.ping()
            return True
        except Exception as e:
            logger.warning(f"InfluxDB ping failed: {e}")
            return False
    
    def close(self) -> None:
        """Close InfluxDB client"""
        if self.client:
            try:
                self.client.close()
            except Exception as e:
                logger.error(f"Error closing InfluxDB: {e}")


# Module-level singleton
influx_service = InfluxService()
