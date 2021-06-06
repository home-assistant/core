"""Tests for the SkyBell integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

USERNAME = "user"
PASSWORD = "password"

CONF_CONFIG_FLOW = {
    CONF_EMAIL: USERNAME,
    CONF_PASSWORD: PASSWORD,
}


async def _create_mocked_skybell(raise_exception=False):
    mocked_skybell = AsyncMock()
    return mocked_skybell


def _patch_config_flow_skybell(mocked_skybell):
    return patch(
        "homeassistant.components.skybell.config_flow.Skybell",
        return_value=mocked_skybell,
    )


def _patch_skybell_login(mocked_skybell):
    return patch(
        "skybellpy.Skybell.login",
        return_value=mocked_skybell,
    )
