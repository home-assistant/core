"""Tests for the metoffice component."""

from datetime import datetime


class MockDateTime(datetime):
    """Replacement for datetime that can be mocked for testing."""

    def __new__(cls, *args, **kwargs):  # pylint: disable=arguments-differ
        """Override to just return base class."""
        return datetime.__new__(datetime, *args, **kwargs)
