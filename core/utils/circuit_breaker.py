"""
Circuit Breaker Pattern for API Reliability
Prevents cascade failures and improves overall system performance
"""

import asyncio
import time
import logging
from typing import Callable, Any, Dict
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"           # Failing, reject calls
    HALF_OPEN = "half_open" # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5        # Failures before opening
    recovery_timeout: int = 60        # Seconds before trying again
    expected_exception: type = Exception
    

class CircuitBreaker:
    """High-performance circuit breaker for API calls"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.success_count = 0
        
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        
        # Check if circuit should be closed
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker: Attempting reset (HALF_OPEN)")
            else:
                raise Exception(f"Circuit breaker OPEN - Service unavailable")
        
        try:
            # Execute the function
            result = await func(*args, **kwargs)
            
            # Success - reset failure count
            self._on_success()
            return result
            
        except self.config.expected_exception as e:
            # Failure - increment counter
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.config.recovery_timeout
    
    def _on_success(self):
        """Handle successful call"""
        if self.state == CircuitState.HALF_OPEN:
            # Reset to normal operation
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            logger.info("Circuit breaker: Service recovered (CLOSED)")
        self.success_count += 1
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if (self.state == CircuitState.CLOSED and 
            self.failure_count >= self.config.failure_threshold):
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker: Too many failures, opening circuit (OPEN)")
        
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker: Half-open test failed, reopening circuit")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_failure_time': self.last_failure_time,
            'is_available': self.state != CircuitState.OPEN
        }


# Pre-configured circuit breakers for common services
telegram_api_breaker = CircuitBreaker(CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=30,
    expected_exception=Exception
))

database_breaker = CircuitBreaker(CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception
))

external_api_breaker = CircuitBreaker(CircuitBreakerConfig(
    failure_threshold=2,
    recovery_timeout=45,
    expected_exception=Exception
))