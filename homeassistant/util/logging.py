"""Logging utilities."""
import logging


class HideSensitiveDataFilter(logging.Filter):
    """Filter API password calls."""

    def __init__(self, text):
        """Initialize sensitive data filter."""
        super().__init__()
        self.text = text

    def filter(self, record):
        """Hide sensitive data in messages."""
        record.msg = record.msg.replace(self.text, '*******')

        return True
