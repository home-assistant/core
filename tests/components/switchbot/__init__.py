"""Tests for the switchbot integration."""
from unittest.mock import patch

from homeassistant.const import CONF_MAC, CONF_NAME, CONF_PASSWORD, CONF_SENSOR_TYPE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DOMAIN = "switchbot"

ENTRY_CONFIG = {
    CONF_NAME: "test-name",
    CONF_PASSWORD: "test-password",
    CONF_MAC: "e7:89:43:99:99:99",
}

USER_INPUT = {
    CONF_NAME: "test-name",
    CONF_PASSWORD: "test-password",
    CONF_MAC: "e7:89:43:99:99:99",
}

USER_INPUT_CURTAIN = {
    CONF_NAME: "test-name",
    CONF_PASSWORD: "test-password",
    CONF_MAC: "e7:89:43:90:90:90",
}

USER_INPUT_UNSUPPORTED_DEVICE = {
    CONF_NAME: "test-name",
    CONF_PASSWORD: "test-password",
    CONF_MAC: "test",
}

USER_INPUT_INVALID = {
    CONF_NAME: "test-name",
    CONF_PASSWORD: "test-password",
    CONF_MAC: "invalid-mac",
}

YAML_CONFIG = {
    CONF_NAME: "test-name",
    CONF_PASSWORD: "test-password",
    CONF_MAC: "e7:89:43:99:99:99",
    CONF_SENSOR_TYPE: "bot",
}


def _patch_async_setup_entry(return_value=True):
    return patch(
        "homeassistant.components.switchbot.async_setup_entry",
        return_value=return_value,
    )


async def init_integration(
    hass: HomeAssistant,
    *,
    data: dict = ENTRY_CONFIG,
    skip_entry_setup: bool = False,
) -> MockConfigEntry:
    """Set up the Switchbot integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)

    if not skip_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
