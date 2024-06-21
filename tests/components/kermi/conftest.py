"""contains pytest fixtures for Kermi tests."""

from unittest.mock import Mock

import pytest

from homeassistant import config_entries
from homeassistant.components.kermi.config_flow import KermiConfigFlow
from homeassistant.components.kermi.water_heater import KermiWaterHeater
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_coordinator():
    """Return a mock DataUpdateCoordinator."""
    return Mock()


@pytest.fixture
def mock_entry():
    """Return a mock ConfigEntry."""
    entry = Mock()
    entry.entry_id = "test_entry_id"
    entry.data = {"water_heater_device_address": "test_address"}
    return entry


@pytest.fixture
def kermi_water_heater(mock_entry, mock_coordinator):
    """Return a KermiWaterHeater instance."""
    return KermiWaterHeater("Test Heater", mock_entry, mock_coordinator)


@pytest.fixture
def hass() -> HomeAssistant:
    """Return a Home Assistant instance."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {}
    hass.config_entries._entries = {}
    return hass


@pytest.fixture
def config_entry():
    """Return a mock ConfigEntry."""
    entry = Mock()
    entry.data = {
        CONF_HOST: "localhost",
        CONF_PORT: 502,
        "water_heater_device_address": 1337,
    }
    return entry


@pytest.fixture
def flow(hass: config_entries.HomeAssistant):
    """Return a KermiConfigFlow."""
    return KermiConfigFlow()
