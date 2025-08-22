"""Common fixtures for the OMIE - Spain and Portugal electricity prices tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.omie.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def hass_lisbon(hass: HomeAssistant):
    """Home Assistant configured for Lisbon timezone."""
    await hass.config.async_set_time_zone("Europe/Lisbon")
    return hass


@pytest.fixture
async def hass_madrid(hass: HomeAssistant):
    """Home Assistant configured for Lisbon timezone."""
    await hass.config.async_set_time_zone("Europe/Madrid")
    return hass
