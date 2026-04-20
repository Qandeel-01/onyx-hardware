"""Redis pub/sub service for WebSocket event broadcasting"""

import asyncio
import json
import logging
import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)


class RedisService:
    """Manages Redis connections for pub/sub messaging"""
    
    def __init__(self):
        """Initialize Redis connection"""
        self._available = False
        self.r = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis client"""
        try:
            # This just creates the connection object, doesn't connect yet
            self.r = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            self._available = True
            logger.info("✓ Redis client created")
        except Exception as e:
            logger.warning(f"⚠ Redis initialization failed: {e}")
            self._available = False
    
    async def publish(self, channel: str, payload: dict) -> None:
        """
        Publish a JSON payload to a Redis channel.
        Gracefully degrades if Redis is unavailable.
        """
        if not self._available or not self.r:
            return
        
        try:
            json_payload = json.dumps(payload)
            await self.r.publish(channel, json_payload)
            
        except Exception as e:
            logger.warning(f"Redis publish to {channel} failed: {e}")
            self._available = False
    
    async def ping(self) -> bool:
        """Health check for Redis"""
        if not self.r:
            return False
        try:
            response = await self.r.ping()
            return bool(response)  # Convert response to boolean
        except Exception as e:
            logger.warning(f"Redis ping failed: {e}")
            return False
    
    async def close(self) -> None:
        """Close Redis connection"""
        if self.r:
            try:
                await self.r.close()
            except Exception as e:
                logger.error(f"Error closing Redis: {e}")


# Module-level singleton
redis_service = RedisService()
