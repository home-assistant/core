"""Fixtures for the Velbus tests."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.velbus.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import PORT_TCP

from tests.common import MockConfigEntry


@pytest.fixture(name="controller")
def mock_controller():
    """Mock a successful velbus controller."""
    controller = AsyncMock()
    with patch("velbusaio.controller.Velbus", return_value=controller):
        yield controller


@pytest.fixture(name="config_entry")
def mock_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create and register mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: PORT_TCP, CONF_NAME: "velbus home"},
    )
    config_entry.add_to_hass(hass)
    return config_entry
