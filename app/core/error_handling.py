"""
Error handling and retry utilities for the 5G Slice Manager.

This module provides decorators and utilities for handling errors and implementing
retry logic with exponential backoff.
"""

import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable, Optional, Type, TypeVar, Union, cast

from app.core.config import settings

T = TypeVar("T")
logger = logging.getLogger(__name__)


class MaxRetriesExceededError(Exception):
    """Raised when the maximum number of retries is exceeded."""

    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.last_exception = last_exception


def async_retry(
    exceptions: Union[Type[Exception], tuple[Type[Exception], ...]] = Exception,
    max_retries: int = None,
    initial_delay: float = None,
    max_delay: float = None,
    backoff_factor: float = None,
):
    """
    Decorator that adds retry logic to async functions with exponential backoff.

    Args:
        exceptions: Exception type(s) to catch and retry on
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Multiplier for exponential backoff
    """
    if max_retries is None:
        max_retries = settings.MAX_RETRY_ATTEMPTS
    if initial_delay is None:
        initial_delay = settings.RETRY_BACKOFF_FACTOR
    if max_delay is None:
        max_delay = settings.RETRY_MAX_DELAY
    if backoff_factor is None:
        backoff_factor = settings.RETRY_BACKOFF_FACTOR

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}",
                            exc_info=True,
                            extra={"attempt": attempt + 1, "max_retries": max_retries},
                        )
                        raise MaxRetriesExceededError(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}",
                            last_exception,
                        ) from e

                    # Add jitter to avoid thundering herd problem
                    jitter = random.uniform(0.5, 1.5)
                    sleep_time = min(delay * jitter, max_delay)

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}. "
                        f"Retrying in {sleep_time:.2f}s...",
                        exc_info=True,
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "sleep_time": sleep_time,
                        },
                    )

                    await asyncio.sleep(sleep_time)
                    delay *= backoff_factor

            # This should never be reached due to the raise in the except block
            raise RuntimeError("Unexpected error in retry logic")  # pragma: no cover

        return cast(Callable[..., T], wrapper)

    return decorator


def sync_retry(
    exceptions: Union[Type[Exception], tuple[Type[Exception], ...]] = Exception,
    max_retries: int = None,
    initial_delay: float = None,
    max_delay: float = None,
    backoff_factor: float = None,
):
    """
    Decorator that adds retry logic to synchronous functions with exponential backoff.

    Args:
        exceptions: Exception type(s) to catch and retry on
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Multiplier for exponential backoff
    """
    if max_retries is None:
        max_retries = settings.MAX_RETRY_ATTEMPTS
    if initial_delay is None:
        initial_delay = settings.RETRY_BACKOFF_FACTOR
    if max_delay is None:
        max_delay = settings.RETRY_MAX_DELAY
    if backoff_factor is None:
        backoff_factor = settings.RETRY_BACKOFF_FACTOR

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}",
                            exc_info=True,
                            extra={"attempt": attempt + 1, "max_retries": max_retries},
                        )
                        raise MaxRetriesExceededError(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}",
                            last_exception,
                        ) from e

                    # Add jitter to avoid thundering herd problem
                    jitter = random.uniform(0.5, 1.5)
                    sleep_time = min(delay * jitter, max_delay)

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}. "
                        f"Retrying in {sleep_time:.2f}s...",
                        exc_info=True,
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "sleep_time": sleep_time,
                        },
                    )

                    time.sleep(sleep_time)
                    delay *= backoff_factor

            # This should never be reached due to the raise in the except block
            raise RuntimeError("Unexpected error in retry logic")  # pragma: no cover

        return wrapper

    return decorator


class DeadLetterQueue:
    """
    A simple in-memory dead letter queue for storing failed operations.
    
    This can be replaced with a persistent storage implementation for production use.
    """

    def __init__(self, max_retries: int = None, retry_delay: int = None):
        """Initialize the dead letter queue.
        
        Args:
            max_retries: Maximum number of retry attempts for each item
            retry_delay: Initial delay between retries in seconds
        """
        self.max_retries = max_retries or settings.DLQ_MAX_RETRIES
        self.retry_delay = retry_delay or settings.DLQ_RETRY_DELAY
        self._queue: list[dict] = []
        self._lock = asyncio.Lock()

    async def put(
        self,
        item: Any,
        error: Exception,
        metadata: Optional[dict] = None,
        context: Optional[dict] = None,
    ) -> None:
        """Add an item to the dead letter queue.
        
        Args:
            item: The item that failed to process
            error: The exception that was raised
            metadata: Additional metadata about the item
            context: Context about when/where the failure occurred
        """
        if not settings.DLQ_ENABLED:
            logger.warning(
                "Dead letter queue is disabled. Failed item will be discarded.",
                extra={"item": str(item), "error": str(error)},
            )
            return

        entry = {
            "item": item,
            "error": str(error),
            "error_type": error.__class__.__name__,
            "metadata": metadata or {},
            "context": context or {},
            "attempts": 0,
            "next_retry": time.time() + self.retry_delay,
            "created_at": time.time(),
            "last_updated": time.time(),
        }

        async with self._lock:
            self._queue.append(entry)

        logger.warning(
            "Item added to dead letter queue",
            extra={
                "item": str(item)[:500],  # Truncate to avoid log flooding
                "error": str(error),
                "queue_size": len(self._queue),
            },
        )

    async def get_retry_items(self) -> list[dict]:
        """Get items that are ready for retry."""
        now = time.time()
        async with self._lock:
            ready_items = [
                item
                for item in self._queue
                if item["attempts"] < self.max_retries
                and item["next_retry"] <= now
            ]
        return ready_items

    async def mark_processed(self, item: dict, success: bool = True) -> None:
        """Mark an item as processed.
        
        Args:
            item: The item to mark as processed
            success: Whether the processing was successful
        """
        async with self._lock:
            if item in self._queue:
                if success:
                    self._queue.remove(item)
                    logger.info(
                        "Item successfully processed and removed from DLQ",
                        extra={"item_id": id(item)},
                    )
                else:
                    item["attempts"] += 1
                    item["last_updated"] = time.time()
                    # Exponential backoff with jitter
                    jitter = random.uniform(0.5, 1.5)
                    item["next_retry"] = time.time() + min(
                        self.retry_delay * (2 ** (item["attempts"] - 1)) * jitter,
                        settings.RETRY_MAX_DELAY,
                    )
                    logger.warning(
                        "Item processing failed, will retry later",
                        extra={
                            "item_id": id(item),
                            "attempts": item["attempts"],
                            "next_retry": item["next_retry"],
                        },
                    )

    async def get_stats(self) -> dict:
        """Get statistics about the dead letter queue."""
        now = time.time()
        async with self._lock:
            return {
                "total_items": len(self._queue),
                "items_pending_retry": sum(
                    1
                    for item in self._queue
                    if item["attempts"] < self.max_retries
                    and item["next_retry"] <= now
                ),
                "items_exceeded_retries": sum(
                    1 for item in self._queue if item["attempts"] >= self.max_retries
                ),
                "oldest_item_age": now - min((item["created_at"] for item in self._queue), default=now),
            }
