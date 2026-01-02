"""Test OPNsense config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.opnsense.const import (
    CONF_API_SECRET,
    CONF_TRACKER_INTERFACES,
    CONF_TRACKER_MAC_ADDRESSES,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_INTERFACES = {"igb0": "WAN", "igb1": "LAN"}
MOCK_DEVICES = [
    {
        "hostname": "Desktop",
        "intf": "igb1",
        "intf_description": "LAN",
        "ip": "192.168.0.167",
        "mac": "ff:ff:ff:ff:ff:fe",
        "manufacturer": "OEM",
    },
    {
        "hostname": "",
        "intf": "igb1",
        "intf_description": "LAN",
        "ip": "192.168.0.123",
        "mac": "ff:ff:ff:ff:ff:ff",
        "manufacturer": "",
    },
]


@pytest.fixture
def mock_opnsense_api():
    """Mock OPNsense API clients."""
    with patch(
        "homeassistant.components.opnsense.config_flow.diagnostics"
    ) as mock_diag:
        interface_client = MagicMock()
        interface_client.get_arp.return_value = MOCK_DEVICES
        mock_diag.InterfaceClient.return_value = interface_client

        netinsight_client = MagicMock()
        netinsight_client.get_interfaces.return_value = MOCK_INTERFACES
        mock_diag.NetworkInsightClient.return_value = netinsight_client

        yield {
            "interface_client": interface_client,
            "netinsight_client": netinsight_client,
        }


async def test_user_flow_success(hass: HomeAssistant, mock_opnsense_api) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://192.168.1.1",
            CONF_API_KEY: "test_key",
            CONF_API_SECRET: "test_secret",
            CONF_VERIFY_SSL: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "interfaces"

    # Select interfaces
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRACKER_INTERFACES: ["LAN"]},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "devices"

    # Select devices
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRACKER_MAC_ADDRESSES: ["ff:ff:ff:ff:ff:fe"]},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "OPNsense https://192.168.1.1/api"
    assert result["data"] == {
        CONF_URL: "https://192.168.1.1/api",
        CONF_API_KEY: "test_key",
        CONF_API_SECRET: "test_secret",
        CONF_VERIFY_SSL: False,
        CONF_TRACKER_INTERFACES: ["LAN"],
        CONF_TRACKER_MAC_ADDRESSES: ["ff:ff:ff:ff:ff:fe"],
    }


async def test_user_flow_no_selection(hass: HomeAssistant, mock_opnsense_api) -> None:
    """Test user flow with no interface or device selection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://192.168.1.1",
            CONF_API_KEY: "test_key",
            CONF_API_SECRET: "test_secret",
            CONF_VERIFY_SSL: False,
        },
    )
    await hass.async_block_till_done()

    # Skip interface selection (empty list)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRACKER_INTERFACES: []},
    )
    await hass.async_block_till_done()

    # Skip device selection (empty list)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRACKER_MAC_ADDRESSES: []},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TRACKER_INTERFACES] == []
    assert result["data"][CONF_TRACKER_MAC_ADDRESSES] == []


async def test_user_flow_connection_error(hass: HomeAssistant) -> None:
    """Test user flow with connection error."""
    from pyopnsense.exceptions import APIException

    with patch(
        "homeassistant.components.opnsense.config_flow.diagnostics"
    ) as mock_diag:
        interface_client = MagicMock()
        interface_client.get_arp.side_effect = APIException("Connection failed")
        mock_diag.InterfaceClient.return_value = interface_client

        netinsight_client = MagicMock()
        netinsight_client.get_interfaces.side_effect = APIException("Connection failed")
        mock_diag.NetworkInsightClient.return_value = netinsight_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "https://192.168.1.1",
                CONF_API_KEY: "test_key",
                CONF_API_SECRET: "test_secret",
                CONF_VERIFY_SSL: False,
            },
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_opnsense_api
) -> None:
    """Test user flow with already configured entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "https://192.168.1.1/api",
            CONF_API_KEY: "test_key",
            CONF_API_SECRET: "test_secret",
        },
        unique_id="https://192.168.1.1/api_test_key",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://192.168.1.1",
            CONF_API_KEY: "test_key",
            CONF_API_SECRET: "test_secret",
            CONF_VERIFY_SSL: False,
        },
    )
    await hass.async_block_till_done()

    # Should proceed to interfaces step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRACKER_INTERFACES: []},
    )
    await hass.async_block_till_done()

    # Should proceed to devices step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRACKER_MAC_ADDRESSES: []},
    )
    await hass.async_block_till_done()

    # Should abort because already configured
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
