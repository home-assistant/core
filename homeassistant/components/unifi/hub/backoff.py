"""Backoff policy for UniFi Network reconnect attempts."""

from dataclasses import dataclass


@dataclass
class BackoffPolicy:
    """Exponential backoff with a cap, keyed by a 0-based attempt count."""

    base: float = 15
    factor: float = 2
    maximum: float = 300

    def next_delay(self, attempt: int) -> float:
        """Return the delay in seconds before the given attempt."""
        return min(self.base * (self.factor**attempt), self.maximum)
