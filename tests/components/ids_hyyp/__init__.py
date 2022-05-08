"""Tests for the ids_hyyp integration."""
from unittest.mock import patch

from homeassistant.components.ids_hyyp.const import CONF_PKG
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DOMAIN = "ids_hyyp"

ENTRY_CONFIG = {
    CONF_EMAIL: "test-email",
    CONF_PASSWORD: "test-password",
    CONF_PKG: "com.hyyp247.home",
}

USER_INPUT = {
    CONF_EMAIL: "test-email",
    CONF_PASSWORD: "test-password",
    CONF_PKG: "com.hyyp247.home",
}

USER_INPUT_INVALID = {
    CONF_EMAIL: "test-email",
    CONF_PASSWORD: "test-password",
    CONF_PKG: "invalid-pkg",
}


def patch_async_setup_entry(return_value=True):
    """Patch async setup entry to return True."""
    return patch(
        "homeassistant.components.ids_hyyp.async_setup_entry",
        return_value=return_value,
    )


async def init_integration(
    hass: HomeAssistant,
    *,
    data: dict = ENTRY_CONFIG,
    skip_entry_setup: bool = False,
) -> MockConfigEntry:
    """Set up the ids_hyyp integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)

    if not skip_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
