"""Tests for the Leviosa Motor Shades Zone integration."""
from homeassistant.components.leviosa_shades.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def configure_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Configure the integration."""
    entry = MockConfigEntry(domain=DOMAIN, entry_id="123456", unique_id="123456")
    entry.add_to_hass(hass)

    return entry
