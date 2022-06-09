"""Tests for the SkyBell integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

USERNAME = "user"
PASSWORD = "password"
USER_ID = "123456789012345678901234"

CONF_CONFIG_FLOW = {
    CONF_EMAIL: USERNAME,
    CONF_PASSWORD: PASSWORD,
}


def _patch_skybell_devices() -> None:
    mocked_skybell = AsyncMock()
    mocked_skybell.user_id = USER_ID
    return patch(
        "homeassistant.components.skybell.config_flow.Skybell.async_get_devices",
        return_value=[mocked_skybell],
    )


def _patch_skybell() -> None:
    return patch(
        "homeassistant.components.skybell.config_flow.Skybell.async_send_request",
        return_value={"id": USER_ID},
    )
