"""Tests for the devolo_home_control integration."""

from homeassistant.components.devolo_home_control.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def configure_integration(hass: HomeAssistant):
    """Configure the integration."""
    config = {
        "username": "test-username",
        "password": "test-password",
        "home_control_url": "https://test_url.test",
        "mydevolo_url": "https://test_mydevolo_url.test",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    return entry
