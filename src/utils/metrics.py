"""
Monitoring and metrics tracking for the multi-agent system.
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
from loguru import logger


class MetricsCollector:
    """Collect and track system metrics."""
    
    def __init__(self):
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.total_response_time = 0.0
        self.total_tokens_used = 0
        self.requests_by_intent = defaultdict(int)
        self.errors_by_type = defaultdict(int)
        self.start_time = datetime.now()
        
    def record_request(
        self,
        success: bool,
        response_time: float,
        intent: Optional[str] = None,
        tokens_used: Optional[int] = None,
        error_type: Optional[str] = None
    ):
        """
        Record a request metric.
        
        Args:
            success: Whether the request was successful
            response_time: Response time in seconds
            intent: Customer intent if available
            tokens_used: Number of tokens used
            error_type: Type of error if failed
        """
        self.request_count += 1
        
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
            if error_type:
                self.errors_by_type[error_type] += 1
        
        self.total_response_time += response_time
        
        if intent:
            self.requests_by_intent[intent] += 1
        
        if tokens_used:
            self.total_tokens_used += tokens_used
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics.
        
        Returns:
            Dictionary of current metrics
        """
        uptime = (datetime.now() - self.start_time).total_seconds()
        avg_response_time = (
            self.total_response_time / self.request_count 
            if self.request_count > 0 
            else 0
        )
        success_rate = (
            (self.success_count / self.request_count * 100)
            if self.request_count > 0
            else 0
        )
        
        return {
            "uptime_seconds": uptime,
            "total_requests": self.request_count,
            "successful_requests": self.success_count,
            "failed_requests": self.error_count,
            "success_rate_percent": round(success_rate, 2),
            "average_response_time_seconds": round(avg_response_time, 3),
            "total_tokens_used": self.total_tokens_used,
            "requests_per_minute": round(self.request_count / (uptime / 60), 2) if uptime > 0 else 0,
            "requests_by_intent": dict(self.requests_by_intent),
            "errors_by_type": dict(self.errors_by_type)
        }
    
    def reset(self):
        """Reset all metrics."""
        self.__init__()
    
    def log_metrics(self):
        """Log current metrics."""
        metrics = self.get_metrics()
        logger.info(f"📊 System Metrics: {metrics}")


class RequestTimer:
    """Context manager for timing requests."""
    
    def __init__(self, name: str = "request"):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.elapsed = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.elapsed = self.end_time - self.start_time
        
        if exc_type is None:
            logger.debug(f"⏱️ {self.name} completed in {self.elapsed:.3f}s")
        else:
            logger.warning(f"⏱️ {self.name} failed after {self.elapsed:.3f}s")
        
        return False  # Don't suppress exceptions
    
    def get_elapsed(self) -> float:
        """Get elapsed time in seconds."""
        return self.elapsed if self.elapsed is not None else 0.0


# Global metrics collector instance
_global_metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return _global_metrics


def record_request_metric(
    success: bool,
    response_time: float,
    intent: Optional[str] = None,
    tokens_used: Optional[int] = None,
    error_type: Optional[str] = None
):
    """
    Record a request metric in the global collector.
    
    Args:
        success: Whether the request was successful
        response_time: Response time in seconds
        intent: Customer intent if available
        tokens_used: Number of tokens used
        error_type: Type of error if failed
    """
    _global_metrics.record_request(
        success=success,
        response_time=response_time,
        intent=intent,
        tokens_used=tokens_used,
        error_type=error_type
    )
