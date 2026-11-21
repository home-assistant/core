"""Tests the services provided by the myUplink integration."""

from unittest.mock import MagicMock, Mock

from aiohttp import ClientResponseError
from probatio import MultipleInvalid
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.myuplink.const import DOMAIN
from homeassistant.components.myuplink.services import (
    MyUplinkService,
    MyUplinkServiceArgument,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceRegistry

from . import setup_integration

TEST_DEVICE = "robin-r-1234-20240201-123456-aa-bb-cc-dd-ee-ff"


async def test_services(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Tests that the custom services are correct."""

    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEVICE), mock_config_entry.entry_id
    )
    await hass.services.async_call(
        DOMAIN,
        MyUplinkService.SET_DATAPOINT,
        {
            ATTR_DEVICE_ID: device.id,
            MyUplinkServiceArgument.DATAPOINT_ID: 99999,
            MyUplinkServiceArgument.VALUE: "value",
        },
        blocking=True,
    )
    mock_myuplink_client.async_set_device_points.assert_called_once_with(
        TEST_DEVICE, data={99999: "value"}
    )


async def test_get_service_api_errors(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service api errors."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEVICE), mock_config_entry.entry_id
    )

    # Test http error
    mock_myuplink_client.async_set_device_points.side_effect = ClientResponseError(
        Mock(), Mock()
    )
    with pytest.raises(HomeAssistantError, match="Failed to set new value"):
        await hass.services.async_call(
            DOMAIN,
            MyUplinkService.SET_DATAPOINT,
            {
                ATTR_DEVICE_ID: device.id,
                MyUplinkServiceArgument.DATAPOINT_ID: 12345,
                MyUplinkServiceArgument.VALUE: "test",
            },
            blocking=True,
        )
    mock_myuplink_client.async_set_device_points.assert_called_once()


async def test_service_validation_errors(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Tests that the custom services handle bad data."""

    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEVICE), mock_config_entry.entry_id
    )

    # Test missing parameters
    with pytest.raises(MultipleInvalid, match="required key not provided"):
        await hass.services.async_call(
            DOMAIN,
            MyUplinkService.SET_DATAPOINT,
            {ATTR_DEVICE_ID: device.id},
            blocking=True,
        )
    mock_myuplink_client.async_set_device_points.assert_not_called()

    # Test invalid device
    with pytest.raises(ServiceValidationError, match="Device with ID invalid_device"):
        await hass.services.async_call(
            DOMAIN,
            MyUplinkService.SET_DATAPOINT,
            {
                ATTR_DEVICE_ID: "invalid_device",
                MyUplinkServiceArgument.DATAPOINT_ID: 12345,
                MyUplinkServiceArgument.VALUE: "test",
            },
            blocking=True,
        )
    mock_myuplink_client.async_set_device_points.assert_not_called()
