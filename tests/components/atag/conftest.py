"""Provide common Atag fixtures."""
import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.atag.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
async def mock_pyatag_sleep():
    """Mock out pyatag sleeps."""
    asyncio_sleep = asyncio.sleep

    async def sleep(duration, loop=None):
        await asyncio_sleep(0)

    with patch("pyatag.gateway.asyncio.sleep", new=sleep):
        yield
