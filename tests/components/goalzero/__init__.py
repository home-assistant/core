"""Tests for the Goal Zero Yeti integration."""

from homeassistant.const import CONF_HOST, CONF_NAME

from tests.async_mock import AsyncMock, patch

HOST = "1.2.3.4"
NAME = "Yeti"

CONF_DATA = {
    CONF_HOST: HOST,
    CONF_NAME: NAME,
}

CONF_CONFIG_FLOW = {
    CONF_HOST: HOST,
    CONF_NAME: NAME,
}


async def _create_mocked_yeti(raise_exception=False):
    mocked_yeti = AsyncMock()
    mocked_yeti.get_state = AsyncMock()
    return mocked_yeti


def _patch_init_yeti(mocked_yeti):
    return patch("homeassistant.components.goalzero.Yeti", return_value=mocked_yeti)


def _patch_config_flow_yeti(mocked_yeti):
    return patch(
        "homeassistant.components.goalzero.config_flow.Yeti",
        return_value=mocked_yeti,
    )
