"""Common test utilities."""

from unittest.mock import Mock


class AsyncMock(Mock):
    """Implements Mock async."""

    async def __call__(self, *args, **kwargs):
        """Hack for async support for Mock."""
        return super().__call__(*args, **kwargs)
