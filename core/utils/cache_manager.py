"""
Smart Caching Layer for Faster API Responses
Reduces redundant API calls and speeds up operations
"""

import asyncio
import time
import json
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheManager:
    """High-performance caching system for API responses"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl_cache: Dict[str, float] = {}
        self._hit_count = 0
        self._miss_count = 0
        
    def _is_expired(self, key: str) -> bool:
        """Check if cache entry is expired"""
        if key not in self._ttl_cache:
            return True
        return time.time() > self._ttl_cache[key]
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key in self._cache and not self._is_expired(key):
            self._hit_count += 1
            return self._cache[key]['data']
        self._miss_count += 1
        return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in cache with TTL (seconds)"""
        self._cache[key] = {
            'data': value,
            'created_at': time.time()
        }
        self._ttl_cache[key] = time.time() + ttl
    
    def delete(self, key: str) -> None:
        """Delete key from cache"""
        self._cache.pop(key, None)
        self._ttl_cache.pop(key, None)
    
    def clear(self) -> None:
        """Clear all cache"""
        self._cache.clear()
        self._ttl_cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries"""
        current_time = time.time()
        expired_keys = [
            key for key, expiry in self._ttl_cache.items()
            if current_time > expiry
        ]
        
        for key in expired_keys:
            self.delete(key)
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._hit_count + self._miss_count
        hit_rate = (self._hit_count / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_entries': len(self._cache),
            'hit_count': self._hit_count,
            'miss_count': self._miss_count,
            'hit_rate': f"{hit_rate:.1f}%",
            'memory_usage': len(str(self._cache))
        }


def cached(ttl: int = 300, key_prefix: str = ""):
    """Decorator for caching function results"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator


# Global cache instance
cache = CacheManager()


# Pre-configured cache decorators for common use cases
@cached(ttl=600, key_prefix="channel")
async def cache_channel_info():
    """Cache channel information for 10 minutes"""
    pass

@cached(ttl=300, key_prefix="account")  
async def cache_account_info():
    """Cache account information for 5 minutes"""
    pass

@cached(ttl=120, key_prefix="api")
async def cache_api_response():
    """Cache API responses for 2 minutes"""
    pass