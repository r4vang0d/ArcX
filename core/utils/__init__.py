"""
High-Performance Utility Modules
Comprehensive performance optimization suite
"""

from .http_client import http_client, OptimizedHTTPClient
from .cache_manager import cache, CacheManager, cached
from .request_batcher import request_batcher, RequestBatcher, Priority, BatchRequest
from .circuit_breaker import CircuitBreaker, telegram_api_breaker, database_breaker, external_api_breaker
from .performance_monitor import performance_monitor, PerformanceMonitor

__all__ = [
    'http_client',
    'OptimizedHTTPClient', 
    'cache',
    'CacheManager',
    'cached',
    'request_batcher',
    'RequestBatcher',
    'Priority',
    'BatchRequest',
    'CircuitBreaker',
    'telegram_api_breaker',
    'database_breaker', 
    'external_api_breaker',
    'performance_monitor',
    'PerformanceMonitor'
]