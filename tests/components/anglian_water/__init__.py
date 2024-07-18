"""Tests for the Anova integration."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.anglian_water import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE_UNIQUE_ID = "abc123def"

CONF_INPUT = {CONF_USERNAME: "sample@gmail.com", CONF_PASSWORD: "sample"}


def create_entry(hass: HomeAssistant, device_id: str = DEVICE_UNIQUE_ID) -> ConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Anglian Water ({CONF_INPUT[CONF_USERNAME]})",
        data=CONF_INPUT,
        unique_id="anglian-water-sample@gmail.com",
        version=1,
    )
    entry.add_to_hass(hass)
    return entry


async def async_init_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
) -> ConfigEntry:
    """Set up the Anglian Water integration in Home Assistant."""

    with patch(
        "homeassistant.components.anglian_water.pyanglianwater.API.create_via_login"
    ):
        entry = create_entry(hass)

        if not skip_setup:
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        return entry
