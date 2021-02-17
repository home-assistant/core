"""Tests for the Phone Modem integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.phone_modem.const import DEFAULT_DEVICE, DEFAULT_NAME
from homeassistant.const import CONF_NAME, CONF_PORT

CONF_DATA = {
    CONF_NAME: DEFAULT_NAME,
    CONF_PORT: DEFAULT_DEVICE,
}


async def _create_mocked_modem(raise_exception=False):
    mocked_yeti = AsyncMock()
    mocked_yeti.get_state = AsyncMock()
    return mocked_yeti


def _patch_config_flow_modem(mocked_modem):
    return patch(
        "homeassistant.components.phone_modem.config_flow.PhoneModem",
        return_value=mocked_modem,
    )
