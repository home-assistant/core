"""Provide common Atag fixtures."""
import asyncio
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
async def mock_pyatag_sleep():
    """Mock out pyatag sleeps."""
    asyncio_sleep = asyncio.sleep

    async def sleep(duration, loop=None):
        await asyncio_sleep(0)

    with patch("pyatag.gateway.asyncio.sleep", new=sleep):
        yield
