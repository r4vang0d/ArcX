"""
Real-time Performance Monitoring
Tracks and optimizes bot performance metrics
"""

import asyncio
import psutil
import time
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Performance metric data point"""
    timestamp: datetime
    value: float
    metric_type: str


class PerformanceMonitor:
    """Real-time performance monitoring and optimization"""
    
    def __init__(self, history_size: int = 1000):
        self.history_size = history_size
        self._metrics: Dict[str, deque] = {}
        self._start_time = time.time()
        self._request_times: deque = deque(maxlen=1000)
        self._active_requests = 0
        self._total_requests = 0
        self._failed_requests = 0
        
    def record_metric(self, metric_type: str, value: float):
        """Record a performance metric"""
        if metric_type not in self._metrics:
            self._metrics[metric_type] = deque(maxlen=self.history_size)
        
        metric = PerformanceMetric(
            timestamp=datetime.now(),
            value=value,
            metric_type=metric_type
        )
        self._metrics[metric_type].append(metric)
    
    def start_request(self) -> float:
        """Start timing a request"""
        self._active_requests += 1
        self._total_requests += 1
        return time.time()
    
    def end_request(self, start_time: float, success: bool = True):
        """End timing a request"""
        duration = time.time() - start_time
        self._request_times.append(duration)
        self._active_requests = max(0, self._active_requests - 1)
        
        if not success:
            self._failed_requests += 1
        
        # Record response time metric
        self.record_metric('response_time', duration)
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system performance metrics"""
        # CPU and Memory
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Network I/O
        network = psutil.net_io_counters()
        
        # Disk I/O
        disk = psutil.disk_io_counters()
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_used_mb': memory.used / (1024 * 1024),
            'memory_available_mb': memory.available / (1024 * 1024),
            'network_bytes_sent': network.bytes_sent,
            'network_bytes_recv': network.bytes_recv,
            'disk_read_bytes': disk.read_bytes if disk else 0,
            'disk_write_bytes': disk.write_bytes if disk else 0,
        }
    
    def get_request_metrics(self) -> Dict[str, Any]:
        """Get request performance metrics"""
        if not self._request_times:
            return {
                'avg_response_time': 0,
                'min_response_time': 0,
                'max_response_time': 0,
                'p95_response_time': 0,
                'requests_per_second': 0,
                'active_requests': self._active_requests,
                'total_requests': self._total_requests,
                'failed_requests': self._failed_requests,
                'success_rate': 100.0
            }
        
        # Calculate statistics
        times = list(self._request_times)
        times.sort()
        
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        p95_time = times[int(len(times) * 0.95)] if times else 0
        
        # Calculate RPS
        uptime = time.time() - self._start_time
        rps = self._total_requests / uptime if uptime > 0 else 0
        
        # Calculate success rate
        success_rate = ((self._total_requests - self._failed_requests) / 
                       self._total_requests * 100) if self._total_requests > 0 else 100
        
        return {
            'avg_response_time': avg_time,
            'min_response_time': min_time,
            'max_response_time': max_time,
            'p95_response_time': p95_time,
            'requests_per_second': rps,
            'active_requests': self._active_requests,
            'total_requests': self._total_requests,
            'failed_requests': self._failed_requests,
            'success_rate': success_rate
        }
    
    def get_optimization_suggestions(self) -> List[str]:
        """Get performance optimization suggestions"""
        suggestions = []
        
        system_metrics = self.get_system_metrics()
        request_metrics = self.get_request_metrics()
        
        # CPU suggestions
        if system_metrics['cpu_percent'] > 80:
            suggestions.append("🔥 High CPU usage - Consider reducing concurrent operations")
        
        # Memory suggestions  
        if system_metrics['memory_percent'] > 85:
            suggestions.append("💾 High memory usage - Consider implementing cache cleanup")
        
        # Response time suggestions
        if request_metrics['avg_response_time'] > 2.0:
            suggestions.append("⏱️ Slow response times - Enable HTTP connection pooling")
        
        # Request rate suggestions
        if request_metrics['requests_per_second'] < 5:
            suggestions.append("⚡ Low request rate - Increase batch sizes")
        
        # Success rate suggestions
        if request_metrics['success_rate'] < 95:
            suggestions.append("❌ High failure rate - Implement circuit breakers")
        
        # Active requests suggestions
        if request_metrics['active_requests'] > 50:
            suggestions.append("🔄 Too many concurrent requests - Add request queuing")
        
        return suggestions
    
    def get_comprehensive_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        return {
            'system_metrics': self.get_system_metrics(),
            'request_metrics': self.get_request_metrics(),
            'optimization_suggestions': self.get_optimization_suggestions(),
            'uptime_seconds': time.time() - self._start_time,
            'monitoring_active': True
        }


# Global performance monitor instance
performance_monitor = PerformanceMonitor()