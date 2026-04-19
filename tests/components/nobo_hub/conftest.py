"""Common fixtures for the Nobø Ecohub tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""

    async def _mock_setup(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        entry.runtime_data = AsyncMock()
        return True

    with patch(
        "homeassistant.components.nobo_hub.async_setup_entry",
        side_effect=_mock_setup,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_unload_entry() -> Generator[AsyncMock]:
    """Override async_unload_entry."""
    with patch(
        "homeassistant.components.nobo_hub.async_unload_entry", return_value=True
    ) as mock_unload_entry:
        yield mock_unload_entry
