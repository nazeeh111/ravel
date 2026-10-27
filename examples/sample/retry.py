"""Retry a transient operation with exponential backoff."""
import time


def retry_with_backoff(operation, attempts=3, initial_delay=0.01):
    """Wait longer between retries when an operation raises OSError."""
    for attempt in range(attempts):
        try:
            return operation()
        except OSError:
            if attempt + 1 == attempts:
                raise
            time.sleep(initial_delay * 2 ** attempt)
