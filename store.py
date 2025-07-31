import json
import logging
import time
from typing import Optional, Union, Any
import redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError


class Store:
    """Redis-based key-value store with retry logic and timeouts"""
    
    def __init__(
        self, 
        host: str = 'localhost', 
        port: int = 6379, 
        db: int = 0,
        socket_connect_timeout: int = 5,
        socket_timeout: int = 5,
        connection_pool_kwargs: Optional[dict] = None,
        retry_times: int = 3,
        retry_delay: float = 0.1
    ):
        """
        Initialize Store with Redis connection
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            socket_connect_timeout: Connection timeout in seconds
            socket_timeout: Socket timeout in seconds
            connection_pool_kwargs: Additional connection pool arguments
            retry_times: Number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.retry_times = retry_times
        self.retry_delay = retry_delay
        
        pool_kwargs = {
            'host': host,
            'port': port,
            'db': db,
            'socket_connect_timeout': socket_connect_timeout,
            'socket_timeout': socket_timeout,
            'decode_responses': True
        }
        
        if connection_pool_kwargs:
            pool_kwargs.update(connection_pool_kwargs)
            
        self.pool = redis.ConnectionPool(**pool_kwargs)
        self._client = None
    
    @property
    def client(self) -> redis.Redis:
        """Lazy client initialization"""
        if self._client is None:
            self._client = redis.Redis(connection_pool=self.pool)
        return self._client
    
    def _retry_operation(self, operation, *args, **kwargs) -> Any:
        """
        Execute operation with retry logic
        
        Args:
            operation: Function to execute
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation
            
        Returns:
            Operation result
            
        Raises:
            Last exception if all retries failed
        """
        last_exception = None
        
        for attempt in range(self.retry_times):
            try:
                return operation(*args, **kwargs)
            except (ConnectionError, TimeoutError) as e:
                last_exception = e
                logging.warning(
                    f"Redis operation failed (attempt {attempt + 1}/{self.retry_times}): {e}"
                )
                if attempt < self.retry_times - 1:
                    time.sleep(self.retry_delay)
                    # Reset client to force new connection
                    self._client = None
            except RedisError as e:
                logging.error(f"Redis error: {e}")
                raise
                
        raise last_exception
    
    def get(self, key: str) -> Optional[str]:
        """
        Get value from persistent storage
        
        Args:
            key: Key to retrieve
            
        Returns:
            Value if exists, None otherwise
            
        Raises:
            RedisError if connection fails after all retries
        """
        return self._retry_operation(self.client.get, key)
    
    def set(self, key: str, value: Union[str, int, float], expire: Optional[int] = None) -> None:
        """
        Set value in persistent storage
        
        Args:
            key: Key to set
            value: Value to store
            expire: Optional expiration time in seconds
            
        Raises:
            RedisError if connection fails after all retries
        """
        if isinstance(value, (int, float)):
            value = str(value)
        elif not isinstance(value, str):
            value = json.dumps(value)
            
        self._retry_operation(self.client.set, key, value, ex=expire)
    
    def cache_get(self, key: str) -> Optional[str]:
        """
        Get value from cache (non-critical operation)
        
        Args:
            key: Key to retrieve
            
        Returns:
            Value if exists and accessible, None otherwise
        """
        try:
            return self._retry_operation(self.client.get, key)
        except Exception as e:
            logging.warning(f"Cache get failed for key {key}: {e}")
            return None
    
    def cache_set(self, key: str, value: Union[str, int, float], expire: Optional[int] = None) -> None:
        """
        Set value in cache (non-critical operation)
        
        Args:
            key: Key to set
            value: Value to store
            expire: Optional expiration time in seconds
        """
        try:
            if isinstance(value, (int, float)):
                value = str(value)
            elif not isinstance(value, str):
                value = json.dumps(value)
                
            self._retry_operation(self.client.set, key, value, ex=expire)
        except Exception as e:
            logging.warning(f"Cache set failed for key {key}: {e}")
    
    def delete(self, key: str) -> None:
        """Delete key from storage"""
        try:
            self._retry_operation(self.client.delete, key)
        except Exception as e:
            logging.warning(f"Delete failed for key {key}: {e}")