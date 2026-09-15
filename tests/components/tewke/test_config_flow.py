"""Test the Tewke config flow."""

import ipaddress
from unittest.mock import AsyncMock, patch

from pytewke.error import PyTewkeDiscoveryError

from homeassistant.components.tewke.const import DOMAIN
from homeassistant.config_entries import SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo


async def test_zeroconf_no_hardware_id(
    hass: HomeAssistant, mock_tap: AsyncMock
) -> None:
    """Test zeroconf discovery aborts if no hardwareId."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ipaddress.ip_address("127.0.0.1"),
            ip_addresses=[ipaddress.ip_address("127.0.0.1")],
            port=5683,
            hostname="tewke-1.local.",
            type="._tewke-coap._udp.local.",
            name="tewke-1._tewke-coap._udp.local.",
            properties={"name": "Tewke Switch"},
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_identify"


async def test_full_zeroconf_flow(hass: HomeAssistant, mock_tap: AsyncMock) -> None:
    """Test full zeroconf discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ipaddress.ip_address("127.0.0.1"),
            ip_addresses=[ipaddress.ip_address("127.0.0.1")],
            port=5683,
            hostname="tewke-1.local.",
            type="._tewke-coap._udp.local.",
            name="tewke-1._tewke-coap._udp.local.",
            properties={
                "hardwareId": "test_dock_id",
                "name": "Tewke Switch",
                "room": "Living Room",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {
        "name": "Tewke Switch",
        "room_suffix": ", in room **Living Room**",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Tewke Switch"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_NAME: "Tewke Switch",
    }
    assert result["options"] == {
        "room_name": "Living Room",
    }
    assert result["result"].unique_id == "test_dock_id"
    mock_tap.close.assert_called_once()


async def test_full_zeroconf_flow_no_room(
    hass: HomeAssistant, mock_tap: AsyncMock
) -> None:
    """Test full zeroconf discovery flow with no room name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ipaddress.ip_address("127.0.0.1"),
            ip_addresses=[ipaddress.ip_address("127.0.0.1")],
            port=5683,
            hostname="tewke-1.local.",
            type="._tewke-coap._udp.local.",
            name="tewke-1._tewke-coap._udp.local.",
            properties={
                "hardwareId": "test_dock_id",
                "name": "Tewke Switch",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {
        "name": "Tewke Switch",
        "room_suffix": "",
    }


async def test_zeroconf_flow_connection_error(
    hass: HomeAssistant, mock_tap: AsyncMock
) -> None:
    """Test zeroconf discovery flow handles connection error."""
    mock_tap.discover.side_effect = [PyTewkeDiscoveryError, None]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ipaddress.ip_address("127.0.0.1"),
            ip_addresses=[ipaddress.ip_address("127.0.0.1")],
            port=5683,
            hostname="tewke-1.local.",
            type="._tewke-coap._udp.local.",
            name="tewke-1._tewke-coap._udp.local.",
            properties={
                "hardwareId": "test_dock_id",
                "name": "Tewke Switch",
                "room": "Living Room",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["errors"] == {"base": "cannot_connect"}
    mock_tap.close.assert_called_once()

    # Recover
    with patch(
        "homeassistant.components.tewke.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Tewke Switch"
    assert mock_tap.discover.call_count == 2
    assert mock_tap.close.call_count == 2


async def test_zeroconf_flow_wrong_device(
    hass: HomeAssistant, mock_tap: AsyncMock
) -> None:
    """Test zeroconf flow aborts if the device hardwareId mismatches."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ipaddress.ip_address("192.168.0.123"),
            ip_addresses=[ipaddress.ip_address("192.168.0.123")],
            hostname="tewke-test.local.",
            name="Tewke Tap._tewke-coap._udp.local.",
            port=5683,
            properties={"hardwareId": "test_dock_id"},
            type="_tewke-coap._udp.local.",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    # Make the device return a different wall_dock_id when connecting
    mock_tap.wall_dock_id = "wrong_dock_id"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "cannot_connect"
    mock_tap.close.assert_called_once()
