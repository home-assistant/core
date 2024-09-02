"""Common fixtures for the Gaposa tests."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant

from tests.common import async_test_home_assistant


@pytest.fixture
async def hass():
    """Return a HomeAssistant instance."""
    async with async_test_home_assistant(asyncio.get_running_loop()) as hass:
        yield hass


@pytest.fixture(autouse=True)
async def verify_cleanup(hass: HomeAssistant) -> None:
    """Verify that the test has cleaned up resources correctly."""

    yield

    await hass.async_stop()


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gaposa.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
