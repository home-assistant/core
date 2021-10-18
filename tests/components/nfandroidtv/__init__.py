"""Tests for the NFAndroidTV integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_HOST, CONF_NAME

HOST = "1.2.3.4"
NAME = "Android TV / Fire TV"

CONF_DATA = {
    CONF_HOST: HOST,
    CONF_NAME: NAME,
}

CONF_CONFIG_FLOW = {
    CONF_HOST: HOST,
    CONF_NAME: NAME,
}


async def _create_mocked_tv(raise_exception=False):
    mocked_tv = AsyncMock()
    mocked_tv.get_state = AsyncMock()
    return mocked_tv


def _patch_config_flow_tv(mocked_tv):
    return patch(
        "homeassistant.components.nfandroidtv.config_flow.Notifications",
        return_value=mocked_tv,
    )
