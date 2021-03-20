"""Test Wallbox Init Component."""
from unittest.mock import MagicMock, patch

from homeassistant.components import wallbox
from homeassistant.components.wallbox.const import CONF_STATION
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME


def test_wallbox_setup_entry():
    """Test Wallbox Setup."""

    MOCK_CONFIG = {
        "data": {
            CONF_USERNAME: "test_username",
            CONF_PASSWORD: "test_password",
            CONF_STATION: "12345",
        }
    }

    hass = MagicMock()

    with patch("wallbox.Wallbox", return_value=True):
        assert wallbox.async_setup_entry(hass, MOCK_CONFIG)


def test_wallbox_unload_entry():
    """Test Wallbox Unload."""

    MOCK_CONFIG = {
        "data": {
            CONF_USERNAME: "test_username",
            CONF_PASSWORD: "test_password",
            CONF_STATION: "12345",
        }
    }

    hass = MagicMock()

    with patch("wallbox.Wallbox", return_value=True):
        assert wallbox.async_unload_entry(hass, MOCK_CONFIG)


def test_wallbox_setup():
    """Test wallbox setup."""
    hass = MagicMock()
    config = MagicMock(return_value="12345")

    assert wallbox.async_setup(hass, config)
