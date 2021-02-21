"""Tests for the Modem Caller ID integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.modem_callerid.const import DEFAULT_DEVICE, DEFAULT_NAME
from homeassistant.const import CONF_DEVICE, CONF_NAME

CONF_DATA = {
    CONF_NAME: DEFAULT_NAME,
    CONF_DEVICE: DEFAULT_DEVICE,
}


async def _create_mocked_modem(raise_exception=False):
    mocked_modem = AsyncMock()
    return mocked_modem


def _patch_config_flow_modem(mocked_modem):
    return patch(
        "homeassistant.components.modem_callerid.config_flow.PhoneModem",
        return_value=mocked_modem,
    )
