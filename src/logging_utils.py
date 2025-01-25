import logging
import time
import functools
from typing import Any, Callable, TypeVar, Generator
from contextlib import contextmanager

logger = logging.getLogger(__name__)

T = TypeVar('T')

def log_timing(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to log at DEBUG level when a function starts
    and ends, and how long it took.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start_time = time.perf_counter()
        logger.debug("Entering function: %s", func.__name__)

        try:
            result = func(*args, **kwargs)
            elapsed_time = time.perf_counter() - start_time
            logger.debug("Exiting function: %s | Elapsed: %.4f seconds",
                         func.__name__, elapsed_time)
            return result
        except Exception as e:
            elapsed_time = time.perf_counter() - start_time
            logger.error("Error in function: %s | Elapsed: %.4f seconds | Error: %s",
                        func.__name__, elapsed_time, str(e))
            raise

    return wrapper

@contextmanager
def log_block_timing(name: str) -> Generator[None, None, None]:
    """Context manager for timing code blocks.

    Args:
        name: Name of the code block for logging
    """
    start_time = time.perf_counter()
    logger.debug("Starting block: %s", name)
    try:
        yield
    finally:
        elapsed_time = time.perf_counter() - start_time
        logger.debug("Finished block: %s | Elapsed: %.4f seconds", name, elapsed_time)

