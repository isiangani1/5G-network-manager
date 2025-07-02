"""
Metrics collection and monitoring for the 5G Slice Manager.

This module provides utilities for collecting and exposing metrics
about the application's performance and health using Prometheus.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    start_http_server as start_prometheus_server,
    REGISTRY,
)
from prometheus_client.metrics import MetricWrapperBase

from app.core.config import settings

# Global metrics registry
METRICS: Dict[str, MetricWrapperBase] = {}


def get_metric(metric_name: str) -> Optional[MetricWrapperBase]:
    """Get a metric by name."""
    return METRICS.get(metric_name)


def register_metric(
    name: str,
    metric_type: Type[Union[Counter, Gauge, Histogram]],
    documentation: str = "",
    labelnames: Optional[List[str]] = None,
    **kwargs,
) -> Union[Counter, Gauge, Histogram]:
    """Register a new metric.
    
    Args:
        name: Metric name (will be prefixed with 'slice_manager_')
        metric_type: Type of metric (Counter, Gauge, or Histogram)
        documentation: Help text for the metric
        labelnames: Optional list of label names
        **kwargs: Additional arguments for the metric constructor
        
    Returns:
        The registered metric
    """
    full_name = f"slice_manager_{name}"
    
    if full_name in METRICS:
        return METRICS[full_name]
    
    if metric_type not in (Counter, Gauge, Histogram):
        raise ValueError(f"Unsupported metric type: {metric_type.__name__}")
    
    # Create the metric with the provided arguments
    metric = metric_type(
        full_name,
        documentation,
        labelnames=labelnames or [],
        **kwargs,
    )
    
    METRICS[full_name] = metric
    return metric


def start_metrics_server(port: Optional[int] = None) -> None:
    """Start the Prometheus metrics server.
    
    Args:
        port: Port to expose metrics on (default: settings.METRICS_PORT)
    """
    if not settings.ENABLE_METRICS:
        return
    
    port = port or settings.METRICS_PORT
    
    try:
        start_prometheus_server(port)
        logger.info(f"Metrics server started on port {port}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")


@dataclass
class Timer:
    """Context manager for measuring code execution time."""
    
    metric_name: str
    labels: Optional[Dict[str, str]] = None
    _start_time: Optional[float] = field(init=False, default=None)
    
    def __enter__(self):
        self._start_time = time.monotonic()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._start_time is not None:
            duration = time.monotonic() - self._start_time
            record_histogram(
                self.metric_name,
                duration,
                labels=self.labels,
            )


def record_counter(
    name: str,
    value: float = 1.0,
    labels: Optional[Dict[str, str]] = None,
) -> None:
    """Record a counter metric.
    
    Args:
        name: Metric name (without 'slice_manager_' prefix)
        value: Value to increment the counter by
        labels: Optional dictionary of label names and values
    """
    metric_name = f"slice_manager_{name}"
    metric = get_metric(metric_name)
    
    if metric is None:
        # Auto-register counter if it doesn't exist
        labelnames = list(labels.keys()) if labels else None
        metric = register_metric(
            name,
            Counter,
            documentation=f"Auto-registered counter for {name}",
            labelnames=labelnames,
        )
    
    if labels:
        metric = metric.labels(**labels)
    
    metric.inc(value)


def record_gauge(
    name: str,
    value: float,
    labels: Optional[Dict[str, str]] = None,
) -> None:
    """Record a gauge metric.
    
    Args:
        name: Metric name (without 'slice_manager_' prefix)
        value: Value to set the gauge to
        labels: Optional dictionary of label names and values
    """
    metric_name = f"slice_manager_{name}"
    metric = get_metric(metric_name)
    
    if metric is None:
        # Auto-register gauge if it doesn't exist
        labelnames = list(labels.keys()) if labels else None
        metric = register_metric(
            name,
            Gauge,
            documentation=f"Auto-registered gauge for {name}",
            labelnames=labelnames,
        )
    
    if labels:
        metric = metric.labels(**labels)
    
    metric.set(value)


def record_histogram(
    name: str,
    value: float,
    labels: Optional[Dict[str, str]] = None,
    buckets: Optional[List[float]] = None,
) -> None:
    """Record a histogram metric.
    
    Args:
        name: Metric name (without 'slice_manager_' prefix)
        value: Value to observe in the histogram
        labels: Optional dictionary of label names and values
        buckets: Optional list of bucket boundaries
    """
    metric_name = f"slice_manager_{name}"
    metric = get_metric(metric_name)
    
    if metric is None:
        # Auto-register histogram if it doesn't exist
        labelnames = list(labels.keys()) if labels else None
        metric = register_metric(
            name,
            Histogram,
            documentation=f"Auto-registered histogram for {name}",
            labelnames=labelnames,
            buckets=buckets or (0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0),
        )
    
    if labels:
        metric = metric.labels(**labels)
    
    metric.observe(value)


# Common metrics
def record_processing_time(
    name: str,
    start_time: float,
    labels: Optional[Dict[str, str]] = None,
) -> None:
    """Record the processing time for an operation.
    
    Args:
        name: Operation name (will be prefixed with 'process_time_')
        start_time: Start time from time.monotonic()
        labels: Optional dictionary of label names and values
    """
    duration = time.monotonic() - start_time
    record_histogram(f"process_time_seconds_{name}", duration, labels=labels)


def record_error(
    error_type: str,
    labels: Optional[Dict[str, str]] = None,
) -> None:
    """Record an error occurrence.
    
    Args:
        error_type: Type of error (e.g., 'validation', 'connection')
        labels: Optional dictionary of additional labels
    """
    if labels is None:
        labels = {}
    
    labels["error_type"] = error_type
    record_counter("errors_total", labels=labels)


# Initialize default metrics on module import
if settings.ENABLE_METRICS:
    # System metrics
    register_metric(
        "process_start_time_seconds",
        Gauge,
        documentation="Start time of the process since unix epoch in seconds",
    ).set_to_current_time()
    
    register_metric(
        "process_cpu_seconds_total",
        Counter,
        documentation="Total user and system CPU time spent in seconds",
    )
    
    register_metric(
        "process_open_fds",
        Gauge,
        documentation="Number of open file descriptors",
    )
    
    register_metric(
        "process_max_fds",
        Gauge,
        documentation="Maximum number of open file descriptors",
    )
    
    # Application-specific metrics
    register_metric(
        "messages_processed_total",
        Counter,
        documentation="Total number of messages processed",
        labelnames=["source", "status"],
    )
    
    register_metric(
        "batch_size",
        Histogram,
        documentation="Size of processed batches",
        buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000),
    )
    
    register_metric(
        "processing_duration_seconds",
        Histogram,
        documentation="Time spent processing batches in seconds",
        buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0),
    )
    
    # Start the metrics server if enabled
    try:
        start_metrics_server()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to start metrics server: {e}")
