"""Tests for the Anova Sous Vide integration."""
from __future__ import annotations

from homeassistant.components.anova_sous_vide.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE_ID = "abc123def"

CONF_INPUT = {"device_id": DEVICE_ID}


def create_entry(hass: HomeAssistant) -> ConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data={"device_id": DEVICE_ID})
    entry.add_to_hass(hass)
    return entry


async def async_init_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
    error: str | None = None,
) -> ConfigEntry:
    """Set up the Slack integration in Home Assistant."""
    entry = create_entry(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
