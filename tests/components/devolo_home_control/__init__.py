"""Tests for the devolo_home_control integration."""
from homeassistant.components.devolo_home_control.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def configure_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Configure the integration."""
    config = {
        "username": "test-username",
        "password": "test-password",
        "mydevolo_url": "https://test_mydevolo_url.test",
    }
    entry = MockConfigEntry(
        domain=DOMAIN, data=config, entry_id="123456", unique_id="123456"
    )
    entry.add_to_hass(hass)

    return entry
