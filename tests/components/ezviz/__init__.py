"""Tests for the EZVIZ integration."""

from unittest.mock import _patch, patch

from homeassistant.components.ezviz.const import (
    ATTR_SERIAL,
    ATTR_TYPE_CAMERA,
    ATTR_TYPE_CLOUD,
    CONF_FFMPEG_ARGUMENTS,
    CONF_RFSESSION_ID,
    CONF_SESSION_ID,
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
    CONF_SESSION_ID: "test-username",
    CONF_RFSESSION_ID: "test-password",
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

USER_INPUT_CAMERA_VALIDATE = {
    ATTR_SERIAL: "C666666",
    CONF_PASSWORD: "test-password",
    CONF_USERNAME: "test-username",
}

USER_INPUT_CAMERA = {
    CONF_PASSWORD: "test-password",
    CONF_USERNAME: "test-username",
    CONF_TYPE: ATTR_TYPE_CAMERA,
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

API_LOGIN_RETURN_VALIDATE = {
    CONF_SESSION_ID: "fake_token",
    CONF_RFSESSION_ID: "fake_rf_token",
    CONF_URL: "apiieu.ezvizlife.com",
    CONF_TYPE: ATTR_TYPE_CLOUD,
}


def patch_async_setup_entry() -> _patch:
    """Patch async_setup_entry."""
    return patch(
        "homeassistant.components.ezviz.async_setup_entry",
        return_value=True,
    )


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the EZVIZ integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG, options=ENTRY_OPTIONS)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
