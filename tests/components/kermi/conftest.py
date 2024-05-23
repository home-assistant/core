"""contains pytest fixtures for Kermi tests."""

from unittest.mock import Mock

import pytest

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant


@pytest.fixture
def hass() -> HomeAssistant:
    """Return a Home Assistant instance."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {}
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
