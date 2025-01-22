import logging
import time
import functools
from contextlib import contextmanager

logger = logging.getLogger(__name__)

def log_timing(func):
    """
    Decorator to log at WARNING level when a function starts
    and ends, and how long it took.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        logger.warning("Entering function: %s", func.__name__)

        try:
            result = func(*args, **kwargs)
            elapsed_time = time.perf_counter() - start_time
            logger.warning("Exiting function: %s | Elapsed: %.4f seconds",
                         func.__name__, elapsed_time)
            return result
        except Exception as e:
            elapsed_time = time.perf_counter() - start_time
            logger.error("Error in function: %s | Elapsed: %.4f seconds | Error: %s",
                        func.__name__, elapsed_time, str(e))
            raise

    return wrapper

@contextmanager
def log_block_timing(name: str):
    """Context manager for timing code blocks.

    Args:
        name: Name of the code block for logging
    """
    start_time = time.perf_counter()
    logger.warning("Starting block: %s", name)
    try:
        yield
    finally:
        elapsed_time = time.perf_counter() - start_time
        logger.warning("Finished block: %s | Elapsed: %.4f seconds", name, elapsed_time)

