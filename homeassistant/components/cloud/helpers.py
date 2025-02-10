"""Helpers for the cloud component."""

import logging
import threading

from homeassistant.core import HomeAssistant


class FixedSizeQueueLogHandler(logging.Handler):
    """Log handler to store messages, with auto rotation."""

    MAX_RECORDS = 500

    def __init__(self) -> None:
        """Initialize a new LogHandler."""
        super().__init__()
        self._records: list[logging.LogRecord] = []
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        """Store log message."""
        with self._lock:
            if len(self._records) >= self.MAX_RECORDS:
                self._records.pop(0)
            self._records.append(record)

    async def get_logs(self, hass: HomeAssistant) -> list[str]:
        """Get stored logs."""

        def _get_logs() -> list[str]:
            with self._lock:
                return [self.format(record) for record in self._records]

        return await hass.async_add_executor_job(_get_logs)
