"""Tests for the Ezviz integration."""
from unittest.mock import patch

from homeassistant.components.ezviz.const import (
    ATTR_SERIAL,
    ATTR_TYPE_CLOUD,
    CONF_FFMPEG_ARGUMENTS,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_TYPE,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_URL: "apiieu.ezvizlife.com",
    CONF_TYPE: ATTR_TYPE_CLOUD,
}

ENTRY_OPTIONS = {
    CONF_FFMPEG_ARGUMENTS: DEFAULT_FFMPEG_ARGUMENTS,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
}

USER_INPUT_VALIDATE = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_URL: "apiieu.ezvizlife.com",
}

USER_INPUT = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_URL: "apiieu.ezvizlife.com",
    CONF_TYPE: ATTR_TYPE_CLOUD,
}

DISCOVERY_INFO = {
    ATTR_SERIAL: "C666666",
    CONF_USERNAME: None,
    CONF_PASSWORD: None,
    CONF_IP_ADDRESS: "127.0.0.1",
}

TEST = {
    CONF_USERNAME: None,
    CONF_PASSWORD: None,
    CONF_IP_ADDRESS: "127.0.0.1",
}


def _patch_async_setup_entry(return_value=True):
    return patch(
        "homeassistant.components.ezviz.async_setup_entry",
        return_value=return_value,
    )


async def init_integration(
    hass: HomeAssistant,
    *,
    data: dict = ENTRY_CONFIG,
    options: dict = ENTRY_OPTIONS,
    skip_entry_setup: bool = False,
) -> MockConfigEntry:
    """Set up the Ezviz integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=data, options=options)
    entry.add_to_hass(hass)

    if not skip_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
