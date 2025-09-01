"""
Request Batching System for Optimal API Performance
Combines multiple API requests for maximum efficiency
"""

import asyncio
import logging
from typing import Dict, List, Any, Callable, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Priority(Enum):
    """Request priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class BatchRequest:
    """Represents a batched request"""
    id: str
    operation: str
    params: Dict[str, Any]
    priority: Priority
    callback: Optional[Callable] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class RequestBatcher:
    """High-performance request batching system"""
    
    def __init__(self, batch_size: int = 20, flush_interval: float = 2.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._queues: Dict[Priority, List[BatchRequest]] = {
            Priority.URGENT: [],
            Priority.HIGH: [],
            Priority.NORMAL: [],
            Priority.LOW: []
        }
        self._processors: Dict[str, Callable] = {}
        self._running = False
        self._batch_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the batching system"""
        self._running = True
        self._batch_task = asyncio.create_task(self._batch_processor())
        logger.info("✅ Request batcher started")
    
    async def stop(self):
        """Stop the batching system"""
        self._running = False
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
        logger.info("✅ Request batcher stopped")
    
    def register_processor(self, operation: str, processor: Callable):
        """Register a processor for an operation type"""
        self._processors[operation] = processor
        logger.info(f"✅ Registered processor for operation: {operation}")
    
    async def add_request(self, request: BatchRequest) -> str:
        """Add a request to the batch queue"""
        self._queues[request.priority].append(request)
        
        # Force flush if urgent or high priority batch is full
        if (request.priority in [Priority.URGENT, Priority.HIGH] and 
            len(self._queues[request.priority]) >= self.batch_size // 2):
            await self._flush_priority_queue(request.priority)
        
        return request.id
    
    async def _batch_processor(self):
        """Main batch processing loop"""
        while self._running:
            try:
                # Process all priority queues
                for priority in [Priority.URGENT, Priority.HIGH, Priority.NORMAL, Priority.LOW]:
                    if self._queues[priority]:
                        await self._flush_priority_queue(priority)
                
                await asyncio.sleep(self.flush_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch processor: {e}")
                await asyncio.sleep(1)
    
    async def _flush_priority_queue(self, priority: Priority):
        """Flush a specific priority queue"""
        queue = self._queues[priority]
        if not queue:
            return
        
        # Group requests by operation type
        operation_groups = {}
        for request in queue:
            if request.operation not in operation_groups:
                operation_groups[request.operation] = []
            operation_groups[request.operation].append(request)
        
        # Process each operation group in parallel
        tasks = []
        for operation, requests in operation_groups.items():
            if operation in self._processors:
                # Split into smaller batches
                for i in range(0, len(requests), self.batch_size):
                    batch = requests[i:i + self.batch_size]
                    task = asyncio.create_task(
                        self._process_batch(operation, batch)
                    )
                    tasks.append(task)
        
        # Execute all batches in parallel
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Clear the queue
        queue.clear()
    
    async def _process_batch(self, operation: str, requests: List[BatchRequest]):
        """Process a batch of requests"""
        try:
            processor = self._processors[operation]
            
            # Extract parameters for batch processing
            batch_params = [req.params for req in requests]
            
            # Execute batch operation
            results = await processor(batch_params)
            
            # Execute callbacks if provided
            for i, request in enumerate(requests):
                if request.callback and i < len(results):
                    try:
                        await request.callback(results[i])
                    except Exception as e:
                        logger.error(f"Error in callback for request {request.id}: {e}")
            
            logger.debug(f"✅ Processed batch of {len(requests)} {operation} requests")
            
        except Exception as e:
            logger.error(f"Error processing {operation} batch: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get batching statistics"""
        total_queued = sum(len(queue) for queue in self._queues.values())
        
        return {
            'total_queued': total_queued,
            'urgent_queue': len(self._queues[Priority.URGENT]),
            'high_queue': len(self._queues[Priority.HIGH]),
            'normal_queue': len(self._queues[Priority.NORMAL]),
            'low_queue': len(self._queues[Priority.LOW]),
            'registered_processors': len(self._processors),
            'running': self._running
        }


# Global batcher instance
request_batcher = RequestBatcher()