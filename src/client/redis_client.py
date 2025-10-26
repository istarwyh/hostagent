import redis
import os
import logging
from typing import Optional, Any, Union
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Redis client wrapper with connection pooling and error handling.
    Follows best practices for production use.
    """

    def __init__(self, url: Optional[str] = None, **kwargs):
        """
        Initialize Redis client.

        Args:
            url: Redis connection URL. If None, uses REDIS_URL env var.
            **kwargs: Additional arguments passed to redis.Redis
        """
        self.url = url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self._client = None
        self._connection_kwargs = kwargs
        self._connect()

    def _connect(self):
        """Establish connection to Redis with error handling."""
        try:
            self._client = redis.Redis.from_url(
                self.url,
                decode_responses=True,  # Return strings instead of bytes
                socket_keepalive=True,   # Keep connections alive
                socket_keepalive_options={},  # Platform-specific TCP keepalive
                retry_on_timeout=True,   # Retry on timeout
                health_check_interval=30,  # Periodic health checks
                **self._connection_kwargs
            )
            # Test connection
            self._client.ping()
            logger.info("Redis connection established successfully")
        except redis.RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    @property
    def client(self) -> redis.Redis:
        """Get the underlying Redis client."""
        if not self._client:
            self._connect()
        return self._client

    def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        try:
            return self.client.get(key)
        except redis.RedisError as e:
            logger.error(f"Redis GET error for key '{key}': {e}")
            return None

    def set(self, key: str, value: Union[str, int, float],
            ex: Optional[int] = None,  # Expire time in seconds
            px: Optional[int] = None,  # Expire time in milliseconds
            nx: bool = False,          # Set only if key doesn't exist
            xx: bool = False           # Set only if key exists
            ) -> bool:
        """Set key-value pair with optional expiration and conditions."""
        try:
            return bool(self.client.set(key, value, ex=ex, px=px, nx=nx, xx=xx))
        except redis.RedisError as e:
            logger.error(f"Redis SET error for key '{key}': {e}")
            return False

    def delete(self, *keys: str) -> int:
        """Delete one or more keys. Returns number of deleted keys."""
        try:
            return self.client.delete(*keys)
        except redis.RedisError as e:
            logger.error(f"Redis DELETE error for keys {keys}: {e}")
            return 0

    def exists(self, *keys: str) -> int:
        """Check if keys exist. Returns number of existing keys."""
        try:
            return self.client.exists(*keys)
        except redis.RedisError as e:
            logger.error(f"Redis EXISTS error for keys {keys}: {e}")
            return 0

    def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key."""
        try:
            return bool(self.client.expire(key, seconds))
        except redis.RedisError as e:
            logger.error(f"Redis EXPIRE error for key '{key}': {e}")
            return False

    def ttl(self, key: str) -> int:
        """Get time-to-live for a key. Returns -2 if key doesn't exist, -1 if no expiration."""
        try:
            return self.client.ttl(key)
        except redis.RedisError as e:
            logger.error(f"Redis TTL error for key '{key}': {e}")
            return -2

    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a key by amount."""
        try:
            return self.client.incr(key, amount)
        except redis.RedisError as e:
            logger.error(f"Redis INCR error for key '{key}': {e}")
            return None

    def decr(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement a key by amount."""
        try:
            return self.client.decr(key, amount)
        except redis.RedisError as e:
            logger.error(f"Redis DECR error for key '{key}': {e}")
            return None

    def keys(self, pattern: str = "*") -> list:
        """Get keys matching pattern. Use with caution on large datasets."""
        try:
            return self.client.keys(pattern)
        except redis.RedisError as e:
            logger.error(f"Redis KEYS error for pattern '{pattern}': {e}")
            return []

    def flushdb(self) -> bool:
        """Flush current database. Use with extreme caution."""
        try:
            self.client.flushdb()
            return True
        except redis.RedisError as e:
            logger.error(f"Redis FLUSHDB error: {e}")
            return False

    def ping(self) -> bool:
        """Test connection to Redis."""
        try:
            return self.client.ping()
        except redis.RedisError as e:
            logger.error(f"Redis PING error: {e}")
            return False

    @contextmanager
    def pipeline(self):
        """Context manager for Redis pipeline operations."""
        pipeline = self.client.pipeline()
        try:
            yield pipeline
            pipeline.execute()
        except redis.RedisError as e:
            logger.error(f"Redis pipeline error: {e}")
            raise

    def close(self):
        """Close Redis connection."""
        if self._client:
            try:
                self._client.close()
                self._client = None
                logger.info("Redis connection closed")
            except redis.RedisError as e:
                logger.error(f"Error closing Redis connection: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience function for quick Redis access
def get_redis_client(url: Optional[str] = None, **kwargs) -> RedisClient:
    """
    Get a Redis client instance.

    Args:
        url: Redis connection URL. If None, uses REDIS_URL env var.
        **kwargs: Additional arguments passed to RedisClient

    Returns:
        RedisClient instance

    Example:
        >>> client = get_redis_client()
        >>> client.set('foo', 'bar')
        >>> value = client.get('foo')
        >>> print(value)  # 'bar'
    """
    return RedisClient(url, **kwargs)