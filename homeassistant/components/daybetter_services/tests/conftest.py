"""Configuration for pytest."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


@pytest.fixture
def mock_setup_entry() -> AsyncMock:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.daybetter_services.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def config_entry() -> ConfigEntry:
    """Create a mock config entry."""
    return ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="DayBetter Services",
        data={
            "user_code": "test_user_code",
            "token": "test_token_12345",
        },
        source="user",
        options={},
        entry_id="test_entry_id",
    )


@pytest.fixture
def hass() -> HomeAssistant:
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.services = MagicMock()
    return hass
