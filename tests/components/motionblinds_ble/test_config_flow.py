"""Test the Motionblinds BLE config flow."""
import socket
from unittest.mock import Mock, patch, AsyncMock

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import dhcp
from homeassistant.components.motionblinds_ble import const
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_MAC = "abcd"
TEST_NAME = f"MOTION_{TEST_MAC.upper()}"
TEST_BLIND_TYPE = const.MotionBlindType.ROLLER
TEST_ADDRESS = "test_adress"

async def test_config_flow_manual_host_success(hass: HomeAssistant) -> None:
    """Successful flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_MAC_CODE: TEST_MAC},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_BLIND_TYPE: const.MotionBlindType.ROLLER},
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == f"MotionBlind {TEST_MAC.upper()}"
    assert result["data"] == {
        const.CONF_ADDRESS: TEST_ADDRESS,
        const.CONF_LOCAL_NAME: TEST_NAME,
        const.CONF_MAC_CODE: TEST_MAC.upper(),
        const.CONF_BLIND_TYPE: TEST_BLIND_TYPE,
    }
    assert result["options"] == {}