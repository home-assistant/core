"""Tests for the UltraSync integration."""
from unittest.mock import patch

from homeassistant.components.ultrasync.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_NAME: "UltraSync",
    CONF_HOST: "127.0.0.1",
    CONF_USERNAME: "User 1",
    CONF_PIN: "1234",
}

ENTRY_OPTIONS = {CONF_SCAN_INTERVAL: 5}

USER_INPUT = {
    CONF_NAME: "UltraSyncUser",
    CONF_HOST: "127.0.0.2",
    CONF_USERNAME: "User 2",
    CONF_PIN: "5678",
}


async def init_integration(
    hass,
    *,
    data: dict = ENTRY_CONFIG,
    options: dict = ENTRY_OPTIONS,
) -> MockConfigEntry:
    """Set up the UltraSync integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=data, options=options)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


def _patch_async_setup(return_value=True):
    return patch(
        "homeassistant.components.ultrasync.async_setup",
        return_value=return_value,
    )


def _patch_async_setup_entry(return_value=True):
    return patch(
        "homeassistant.components.ultrasync.async_setup_entry",
        return_value=return_value,
    )
