"""Tests for the Goal Zero Yeti integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.goalzero.const import DEFAULT_NAME
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SCAN_INTERVAL

HOST = "1.2.3.4"
SCAN_INTERVAL = 30

CONF_DATA = {
    CONF_HOST: HOST,
    CONF_NAME: DEFAULT_NAME,
    CONF_SCAN_INTERVAL: SCAN_INTERVAL,
}


async def _create_mocked_yeti(raise_exception=False):
    mocked_yeti = AsyncMock()
    mocked_yeti.get_state = AsyncMock()
    return mocked_yeti


def _patch_config_flow_yeti(mocked_yeti):
    return patch(
        "homeassistant.components.goalzero.config_flow.Yeti",
        return_value=mocked_yeti,
    )
