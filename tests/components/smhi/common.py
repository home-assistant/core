"""Common test utilities."""
from unittest.mock import Mock


class AsyncMock(Mock):
    """Implements Mock async."""

    # pylint: disable=W0235
    async def __call__(self, *args, **kwargs):
        """Hack for async support for Mock."""
        return super(AsyncMock, self).__call__(*args, **kwargs)
