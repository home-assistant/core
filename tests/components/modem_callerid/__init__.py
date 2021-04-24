"""Tests for the Modem Caller ID integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.modem_callerid.const import DEFAULT_DEVICE
from homeassistant.const import CONF_DEVICE

CONF_DATA = {
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
