"""Tests for the devolo_spencer_control integration."""

from spencerassistant.components.devolo_spencer_control.const import DOMAIN
from spencerassistant.core import spencerAssistant

from tests.common import MockConfigEntry


def configure_integration(hass: spencerAssistant) -> MockConfigEntry:
    """Configure the integration."""
    config = {
        "username": "test-username",
        "password": "test-password",
        "mydevolo_url": "https://test_mydevolo_url.test",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config, unique_id="123456")
    entry.add_to_hass(hass)

    return entry
