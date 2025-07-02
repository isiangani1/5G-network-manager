"""
Batch processing utilities for the 5G Slice Manager.

This module provides a batch processor that can efficiently process items in batches
with configurable batch sizes and timeouts.
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Deque, List, Optional, TypeVar, Union

from app.core.config import settings
from app.core.error_handling import async_retry, sync_retry

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class BatchResult:
    """Result of processing a batch of items."""

    success: bool
    processed_count: int = 0
    failed_count: int = 0
    errors: List[Exception] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class BatchProcessor:
    """Processes items in batches with configurable batch size and timeouts."""

    def __init__(
        self,
        process_batch: Callable[[List[T]], R],
        batch_size: int = None,
        max_wait_seconds: float = None,
        retry_attempts: int = None,
        retry_delay: float = None,
    ):
        """Initialize the batch processor.

        Args:
            process_batch: Function to process a batch of items
            batch_size: Maximum number of items in a batch
            max_wait_seconds: Maximum seconds to wait before processing a partial batch
            retry_attempts: Number of retry attempts for failed batches
            retry_delay: Delay between retry attempts in seconds
        """
        self.process_batch = process_batch
        self.batch_size = batch_size or settings.STREAM_BATCH_SIZE
        self.max_wait_seconds = max_wait_seconds or settings.STREAM_MAX_BATCH_WAIT
        self.retry_attempts = retry_attempts or settings.MAX_RETRY_ATTEMPTS
        self.retry_delay = retry_delay or settings.RETRY_BACKOFF_FACTOR

        self._queue: Deque[T] = deque()
        self._last_processed = time.monotonic()
        self._shutdown = False
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        self._background_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background processing task."""
        if self._background_task is None:
            self._shutdown = False
            self._background_task = asyncio.create_task(self._process_batches())

    async def stop(self) -> None:
        """Stop the background processing task and process any remaining items."""
        if self._background_task:
            self._shutdown = True
            async with self._lock:
                self._not_empty.notify_all()
            await self._background_task
            self._background_task = None

    async def add_item(self, item: T) -> None:
        """Add an item to the processing queue.

        Args:
            item: The item to add to the queue
        """
        async with self._lock:
            self._queue.append(item)
            if len(self._queue) >= self.batch_size:
                self._not_empty.notify()

    async def _get_batch(self) -> List[T]:
        """Get a batch of items to process."""
        async with self._lock:
            # Wait until we have at least one item or the shutdown flag is set
            while not self._queue and not self._shutdown:
                await self._not_empty.wait()

            if self._shutdown and not self._queue:
                return []

            # Get up to batch_size items
            batch_size = min(len(self._queue), self.batch_size)
            batch = [self._queue.popleft() for _ in range(batch_size)]
            return batch

    @async_retry(max_retries=3)
    async def _process_batch(self, batch: List[T]) -> BatchResult:
        """Process a batch of items.

        Args:
            batch: The batch of items to process

        Returns:
            BatchResult with the result of processing the batch
        """
        if not batch:
            return BatchResult(success=True)

        start_time = time.monotonic()
        result = BatchResult(success=True)

        try:
            # Call the process_batch function with the batch
            if asyncio.iscoroutinefunction(self.process_batch):
                await self.process_batch(batch)
            else:
                self.process_batch(batch)

            result.processed_count = len(batch)
            result.metadata["processing_time"] = time.monotonic() - start_time

        except Exception as e:
            result.success = False
            result.failed_count = len(batch)
            result.errors.append(e)
            result.metadata["error"] = str(e)
            result.metadata["processing_time"] = time.monotonic() - start_time
            raise  # Will be caught by the retry decorator

        return result

    async def _process_batches(self) -> None:
        """Process batches of items in a loop."""
        while not self._shutdown:
            try:
                # Wait for a batch to be ready
                batch = await self._get_batch()
                if not batch and self._shutdown:
                    break

                # Process the batch with retry logic
                result = await self._process_batch(batch)

                # Log the result
                if result.success:
                    logger.info(
                        "Successfully processed batch",
                        extra={
                            "batch_size": len(batch),
                            "processing_time": result.metadata.get("processing_time", 0),
                        },
                    )
                else:
                    logger.error(
                        "Failed to process batch",
                        extra={
                            "batch_size": len(batch),
                            "error": result.metadata.get("error", "Unknown error"),
                            "processing_time": result.metadata.get("processing_time", 0),
                        },
                    )

            except asyncio.CancelledError:
                # Handle cancellation
                logger.info("Batch processing task was cancelled")
                raise
            except Exception as e:
                logger.error("Error in batch processing loop", exc_info=True)
                # Add a small delay to prevent tight loops on repeated errors
                await asyncio.sleep(1)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()


# Example usage:
if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    async def example_processor(batch):
        print(f"Processing batch of {len(batch)} items")
        await asyncio.sleep(0.5)  # Simulate work
        if "fail" in batch:
            raise ValueError("Simulated error")

    async def main():
        processor = BatchProcessor(example_processor, batch_size=3, max_wait_seconds=2)
        
        # Start the processor
        await processor.start()
        
        # Add some items
        for i in range(10):
            await processor.add_item(f"item-{i}")
        
        # Add a failing item
        await processor.add_item("fail")
        
        # Wait for processing to complete
        await asyncio.sleep(5)
        
        # Stop the processor
        await processor.stop()

    asyncio.run(main())
