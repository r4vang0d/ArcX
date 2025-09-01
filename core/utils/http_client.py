"""
Optimized HTTP Client with Connection Pooling
High-performance HTTP client for faster API requests
"""

import asyncio
import httpx
import logging
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class OptimizedHTTPClient:
    """High-performance HTTP client with connection pooling and optimizations"""
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self._session_cache: Dict[str, httpx.AsyncClient] = {}
        
    async def initialize(self):
        """Initialize optimized HTTP client"""
        # Connection limits for optimal performance
        limits = httpx.Limits(
            max_keepalive_connections=100,  # Keep connections alive
            max_connections=200,            # Total connection pool
            keepalive_expiry=300           # 5 minutes keep-alive
        )
        
        # Timeout configuration
        timeout = httpx.Timeout(
            connect=10.0,    # Connection timeout
            read=30.0,       # Read timeout  
            write=10.0,      # Write timeout
            pool=10.0        # Pool acquisition timeout
        )
        
        # Create optimized client
        self.client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            http2=True,                    # Enable HTTP/2 for speed
            follow_redirects=True,         # Handle redirects automatically
            verify=True                    # SSL verification
        )
        
        logger.info("✅ Optimized HTTP client initialized")
    
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Optimized GET request"""
        if not self.client:
            await self.initialize()
        return await self.client.get(url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """Optimized POST request"""
        if not self.client:
            await self.initialize()
        return await self.client.post(url, **kwargs)
    
    async def batch_requests(self, requests: List[Dict[str, Any]]) -> List[httpx.Response]:
        """Execute multiple HTTP requests concurrently"""
        if not self.client:
            await self.initialize()
            
        async def make_request(req):
            method = req.get('method', 'GET').upper()
            if method == 'GET':
                return await self.client.get(req['url'], **req.get('kwargs', {}))
            elif method == 'POST':
                return await self.client.post(req['url'], **req.get('kwargs', {}))
            
        # Execute all requests concurrently
        tasks = [make_request(req) for req in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def close(self):
        """Close HTTP client and cleanup connections"""
        if self.client:
            await self.client.aclose()
        for client in self._session_cache.values():
            await client.aclose()


# Global optimized HTTP client instance
http_client = OptimizedHTTPClient()