"""Tests for the Happiest Baby Snoo integration."""

from homeassistant.components.snoo.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def create_entry(
    hass: HomeAssistant,
) -> ConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test-username",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "sample",
        },
        # This is also gotten from the fake jwt
        unique_id="123e4567-e89b-12d3-a456-426614174000",
        version=1,
    )
    entry.add_to_hass(hass)
    return entry


async def async_init_integration(hass: HomeAssistant) -> ConfigEntry:
    """Set up the Snoo integration in Home Assistant."""

    entry = create_entry(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
