"""Test the Tewke config flow."""

import ipaddress
from unittest.mock import AsyncMock, patch

import pytest
from pytewke.error import PyTewkeDiscoveryError

from homeassistant.components.tewke.const import DOMAIN
from homeassistant.config_entries import SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo


@pytest.fixture
def mock_tap():
    """Mock pytewke.Tap."""
    with patch(
        "homeassistant.components.tewke.config_flow.pytewke.Tap", autospec=True
    ) as mock_tap:
        tap_instance = mock_tap.return_value
        tap_instance.resources = {}
        tap_instance.discover = AsyncMock()
        tap_instance.get_scenes = AsyncMock(return_value={"scene1": "Mock Scene"})
        tap_instance.close = AsyncMock()
        yield mock_tap


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
                "hardwareId": "12345",
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirmation"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Tewke Switch"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_NAME: "Tewke Switch",
        "room_name": "Living Room",
        "scenes": {"scene1": "Mock Scene"},
    }
    assert result["result"].unique_id == "12345"


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
                "hardwareId": "12345",
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
    tap_1 = AsyncMock()
    tap_1.resources = {}
    tap_1.discover.side_effect = PyTewkeDiscoveryError
    tap_2 = AsyncMock()
    tap_2.resources = {}
    tap_2.get_scenes.return_value = {"scene1": "Mock Scene"}
    mock_tap.side_effect = [tap_1, tap_2]

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
                "hardwareId": "12345",
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
    assert result["step_id"] == "confirmation"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirmation"
    assert result["errors"] == {"base": "cannot_connect"}
    tap_1.close.assert_called_once()

    # Recover
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Tewke Switch"
    tap_2.discover.assert_called_once()
