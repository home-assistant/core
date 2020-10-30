"""Tests for the UltraSync integration."""
from datetime import timedelta

from homeassistant.components.ultrasync.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)

from tests.async_mock import patch
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

YAML_CONFIG = {
    CONF_NAME: "UltraSyncYAML",
    CONF_HOST: "127.0.0.3",
    CONF_USERNAME: "User 3",
    CONF_PIN: "9876",
    CONF_SCAN_INTERVAL: timedelta(seconds=5),
}

MOCK_VERSION = "21.0"

MOCK_AREAS = [
    {"bank": 0, "name": "Area 1", "sequence": 30, "status": "Ready"},
]


MOCK_ZONES = [
    {"bank": 0, "name": "Front door", "sequence": 1, "status": "Ready"},
    {"bank": 1, "name": "Back door", "sequence": 1, "status": "Ready"},
]


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
