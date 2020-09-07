"""Tests for the Goal Zero Yeti integration."""
from goalzero import exceptions

from homeassistant.const import CONF_HOST, CONF_NAME

from tests.async_mock import AsyncMock, patch

HOST = "1.2.3.4"
FAKE_HOST = "1.2.3.5"
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
    type(mocked_yeti).get_data = AsyncMock(
        side_effect=exceptions.ConnectError("") if raise_exception else None
    )
    type(mocked_yeti).enable = AsyncMock()
    type(mocked_yeti).disable = AsyncMock()
    return mocked_yeti


def _patch_init_yeti(mocked_yeti):
    return patch("homeassistant.components.goalzero.GoalZero", return_value=mocked_yeti)


def _patch_config_flow_yeti(mocked_yeti):
    return patch(
        "homeassistant.components.goalzero.config_flow.GoalZero",
        return_value=mocked_yeti,
    )
