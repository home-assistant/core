"""Test the Motionblinds BLE config flow."""
import socket
from unittest.mock import Mock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import dhcp
from homeassistant.components.motionblinds_ble import const
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_MAC = "ab:cd:ef:gh"


@pytest.fixture(name="motionblinds_ble_connect", autouse=True)
def motion_blinds_connect_fixture(mock_get_source_ip):
    """Mock motion blinds ble connection and entry setup."""
    with patch(
        "homeassistant.components.motionblinds_ble.config_flow.bluetooth.async_scanner_count",
        return_value=1,
    ), patch(
        "homeassistant.components.motion_blinds_ble.async_setup_entry", return_value=True
    ):
        yield


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
        {CONF_MAC_CODE: TEST_MAC},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "connect"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MAC_CODE: TEST_MAC},
    )
