"""Test UPnP/IGD config flow."""

from asynctest import patch

from homeassistant import data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.upnp.const import (
    DISCOVERY_LOCATION,
    DISCOVERY_ST,
    DISCOVERY_UDN,
    DISCOVERY_USN,
    DOMAIN,
)
from homeassistant.components.upnp.device import Device
from homeassistant.helpers.typing import HomeAssistantType

from .mock_device import MockDevice

from tests.common import mock_coro


async def test_flow_ssdp_discovery(hass: HomeAssistantType):
    """Test config flow: discovered + configured through ssdp."""
    # Discovered via step ssdp.
    udn = "uuid:device_1"
    mock_device = MockDevice(udn)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "ssdp"},
        data={
            ssdp.ATTR_SSDP_ST: mock_device.device_type,
            ssdp.ATTR_UPNP_UDN: mock_device.udn,
            "friendlyName": mock_device.name,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "ssdp_confirm"

    # Confirm via step ssdp_confirm.
    with patch.object(Device, "async_create_device") as create_device, patch.object(
        Device, "async_discover"
    ) as async_discover:
        create_device.return_value = mock_coro(return_value=mock_device)
        async_discover.return_value = mock_coro(
            return_value=[
                {
                    DISCOVERY_ST: mock_device.device_type,
                    DISCOVERY_UDN: mock_device.udn,
                    DISCOVERY_LOCATION: "dummy",
                }
            ]
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == mock_device.name
        assert result["data"] == {
            "st": mock_device.device_type,
            "udn": mock_device.udn,
        }


async def test_flow_user(hass: HomeAssistantType):
    """Test config flow: discovered + configured through user."""
    udn = "uuid:device_1"
    mock_device = MockDevice(udn)
    usn = f"{mock_device.udn}::{mock_device.device_type}"

    with patch.object(Device, "async_create_device") as create_device, patch.object(
        Device, "async_discover"
    ) as async_discover:
        # Discovered via step user.
        async_discover.return_value = mock_coro(
            return_value=[
                {
                    DISCOVERY_USN: usn,
                    DISCOVERY_ST: mock_device.device_type,
                    DISCOVERY_UDN: mock_device.udn,
                    DISCOVERY_LOCATION: "dummy",
                }
            ]
        )
        create_device.return_value = mock_coro(return_value=mock_device)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        # Confirmed via step user.
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"usn": usn},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == mock_device.name
        assert result["data"] == {
            "st": mock_device.device_type,
            "udn": mock_device.udn,
        }


async def test_flow_config(hass: HomeAssistantType):
    """Test config flow: discovered + configured through configuration.yaml."""
    udn = "uuid:device_1"
    mock_device = MockDevice(udn)
    usn = f"{mock_device.udn}::{mock_device.device_type}"

    with patch.object(Device, "async_create_device") as create_device, patch.object(
        Device, "async_discover"
    ) as async_discover:
        # Discovered via step import.
        async_discover.return_value = mock_coro(
            return_value=[
                {
                    DISCOVERY_USN: usn,
                    DISCOVERY_ST: mock_device.device_type,
                    DISCOVERY_UDN: mock_device.udn,
                    DISCOVERY_LOCATION: "dummy",
                }
            ]
        )
        create_device.return_value = mock_coro(return_value=mock_device)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == mock_device.name
        assert result["data"] == {
            "st": mock_device.device_type,
            "udn": mock_device.udn,
        }
