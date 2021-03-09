"""Tests for the Ezviz integration."""
from unittest.mock import patch

from homeassistant.components.ezviz.const import (
    ATTR_CAMERAS,
    ATTR_SERIAL,
    ATTR_TYPE_CAMERA,
    ATTR_TYPE_CLOUD,
    CONF_FFMPEG_ARGUMENTS,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_REGION,
    CONF_TIMEOUT,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_REGION: "test-region",
    CONF_TIMEOUT: 25,
}

ENTRY_OPTIONS = {
    CONF_FFMPEG_ARGUMENTS: DEFAULT_FFMPEG_ARGUMENTS,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
}

USER_INPUT_VALIDATE = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_REGION: "test-region",
}

USER_INPUT = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_REGION: "test-region",
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

YAML_CONFIG = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_REGION: "test-region",
    ATTR_CAMERAS: {
        "C666666": {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"}
    },
}

YAML_INVALID = {
    "C666666": {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"}
}

YAML_CONFIG_CAMERA = {
    ATTR_SERIAL: "C666666",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


def _patch_async_setup(return_value=True):
    return patch(
        "homeassistant.components.ezviz.async_setup",
        return_value=return_value,
    )


def _patch_async_setup_entry(return_value=True):
    return patch(
        "homeassistant.components.ezviz.async_setup_entry",
        return_value=return_value,
    )


async def init_integration(
    hass: HomeAssistantType,
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
