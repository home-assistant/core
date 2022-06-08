"""Tests for the SkyBell integration."""

from unittest.mock import AsyncMock, patch

from aioskybell import SkybellDevice

from homeassistant.components.skybell.const import CONF_MACS
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

USERNAME = "user"
PASSWORD = "password"
USER_ID = "123456789012345678901234"
MAC = "aa:bb:cc:dd:ee:ff"

CONF_CONFIG_FLOW = {
    CONF_EMAIL: USERNAME,
    CONF_PASSWORD: PASSWORD,
}

CONF_DATA = CONF_CONFIG_FLOW | {CONF_MACS: [MAC]}


def _patch_skybell_devices() -> None:
    mocked_skybell = AsyncMock()
    mocked_skybell.user_id = USER_ID
    device = SkybellDevice({}, mocked_skybell)
    device._info_json["mac"] = MAC
    return patch(
        "homeassistant.components.skybell.config_flow.Skybell.async_get_devices",
        return_value=[device],
    )


def _patch_update() -> None:
    return patch("aioskybell.device.SkybellDevice.async_update")


def _patch_skybell() -> None:
    return patch(
        "homeassistant.components.skybell.config_flow.Skybell.async_send_request",
        return_value={"id": USER_ID},
    )
