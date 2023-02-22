"""Utilities for MJPEG IP Camera."""

import logging


class NoHeaderErrorFilter(logging.Filter):
    """Filter out urllib3 Header Parsing Errors due to a urllib3 bug."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out Header Parsing Errors."""
        return "Failed to parse headers" not in record.getMessage()


def filter_urllib3_logging() -> None:
    """Filter header errors from urllib3 due to a urllib3 bug."""
    urllib3_logger = logging.getLogger("urllib3.connectionpool")
    if not any(isinstance(x, NoHeaderErrorFilter) for x in urllib3_logger.filters):
        urllib3_logger.addFilter(NoHeaderErrorFilter())
