"""Test UPnP/IGD config flow."""

from homeassistant import config_entries, data_entry_flow
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

from tests.async_mock import AsyncMock, patch


async def test_flow_ssdp_discovery(hass: HomeAssistantType):
    """Test config flow: discovered + configured through ssdp."""
    udn = "uuid:device_1"
    mock_device = MockDevice(udn)
    discovery_infos = [
        {
            DISCOVERY_ST: mock_device.device_type,
            DISCOVERY_UDN: mock_device.udn,
            DISCOVERY_LOCATION: "dummy",
        }
    ]
    with patch.object(
        Device, "async_create_device", AsyncMock(return_value=mock_device)
    ), patch.object(Device, "async_discover", AsyncMock(return_value=discovery_infos)):
        # Discovered via step ssdp.
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data={
                ssdp.ATTR_SSDP_ST: mock_device.device_type,
                ssdp.ATTR_UPNP_UDN: mock_device.udn,
                "friendlyName": mock_device.name,
            },
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "ssdp_confirm"

        # Confirm via step ssdp_confirm.
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
    discovery_infos = [
        {
            DISCOVERY_USN: usn,
            DISCOVERY_ST: mock_device.device_type,
            DISCOVERY_UDN: mock_device.udn,
            DISCOVERY_LOCATION: "dummy",
        }
    ]

    with patch.object(
        Device, "async_create_device", AsyncMock(return_value=mock_device)
    ), patch.object(Device, "async_discover", AsyncMock(return_value=discovery_infos)):
        # Discovered via step user.
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
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
    discovery_infos = [
        {
            DISCOVERY_USN: usn,
            DISCOVERY_ST: mock_device.device_type,
            DISCOVERY_UDN: mock_device.udn,
            DISCOVERY_LOCATION: "dummy",
        }
    ]

    with patch.object(
        Device, "async_create_device", AsyncMock(return_value=mock_device)
    ), patch.object(Device, "async_discover", AsyncMock(return_value=discovery_infos)):
        # Discovered via step import.
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == mock_device.name
        assert result["data"] == {
            "st": mock_device.device_type,
            "udn": mock_device.udn,
        }
