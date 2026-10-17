"""Tests the services provided by the myUplink integration."""

from unittest.mock import MagicMock, Mock

from aiohttp import ClientResponseError
from probatio import MultipleInvalid
import pytest

from homeassistant.components.myuplink.const import DOMAIN
from homeassistant.components.myuplink.services import (
    ATTR_DATAPOINT_ID,
    ATTR_VALUE,
    SERVICE_SET_DATAPOINT,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceRegistry

from . import setup_integration

from tests.common import MockConfigEntry

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
        SERVICE_SET_DATAPOINT,
        {
            ATTR_DEVICE_ID: device.id,
            ATTR_DATAPOINT_ID: 99999,
            ATTR_VALUE: "value",
        },
        blocking=True,
    )
    mock_myuplink_client.async_set_device_points.assert_called_once_with(
        TEST_DEVICE, data={99999: "value"}
    )


# @pytest.mark.parametrize(
#     ("call_arguments", "myuplink_arguments"),
#     [
#         (
#             {ATTR_PROGRAM_ID: 24},
#             {"programId": 24},
#         ),
#         (
#             {ATTR_PROGRAM_ID: 25, ATTR_DURATION: timedelta(minutes=75)},
#             {"programId": 25, "duration": [1, 15]},
#         ),
#         (
#             {
#                 ATTR_PROGRAM_ID: 26,
#                 ATTR_DURATION: timedelta(minutes=135),
#                 ATTR_TEMPERATURE: 180,
#             },
#             {"programId": 26, "duration": [2, 15], "temperature": 180},
#         ),
#     ],
# )
# async def test_services_oven(
#     hass: HomeAssistant,
#     device_registry: DeviceRegistry,
#     mock_myuplink_client: MagicMock,
#     mock_config_entry: MockConfigEntry,
#     call_arguments: dict,
#     myuplink_arguments: dict,
# ) -> None:
#     """Tests that the custom services are correct for ovens."""

#     await setup_integration(hass, mock_config_entry)
#     device = device_registry.async_get_device_by_identifier(
#         (DOMAIN, TEST_APPLIANCE), mock_config_entry.entry_id
#     )
#     await hass.services.async_call(
#         DOMAIN,
#         SERVICE_SET_PROGRAM_OVEN,
#         {ATTR_DEVICE_ID: device.id, **call_arguments},
#         blocking=True,
#     )
#     mock_myuplink_client.set_program.assert_called_once_with(
#         TEST_APPLIANCE, myuplink_arguments
#     )


# async def test_services_with_response(
#     hass: HomeAssistant,
#     device_registry: DeviceRegistry,
#     mock_myuplink_client: MagicMock,
#     mock_config_entry: MockConfigEntry,
#     snapshot: SnapshotAssertion,
# ) -> None:
#     """Tests that the custom services that returns a response are correct."""

#     await setup_integration(hass, mock_config_entry)
#     device = device_registry.async_get_device_by_identifier(
#         (DOMAIN, TEST_APPLIANCE), mock_config_entry.entry_id
#     )
#     assert snapshot == await hass.services.async_call(
#         DOMAIN,
#         SERVICE_GET_PROGRAMS,
#         {
#             ATTR_DEVICE_ID: device.id,
#         },
#         blocking=True,
#         return_response=True,
#     )


# @pytest.mark.parametrize(
#     ("service", "error"),
#     [
#         (SERVICE_SET_PROGRAM, "'Set program' action failed"),
#         (SERVICE_SET_PROGRAM_OVEN, "'Set program on oven' action failed"),
#     ],
# )
# async def test_service_api_errors(
#     hass: HomeAssistant,
#     device_registry: DeviceRegistry,
#     mock_myuplink_client: MagicMock,
#     mock_config_entry: MockConfigEntry,
#     service: str,
#     error: str,
# ) -> None:
#     """Test service api errors."""
#     await setup_integration(hass, mock_config_entry)
#     device = device_registry.async_get_device_by_identifier(
#         (DOMAIN, TEST_APPLIANCE), mock_config_entry.entry_id
#     )

#     # Test http error
#     mock_myuplink_client.set_program.side_effect = ClientResponseError(Mock(), Mock())
#     with pytest.raises(HomeAssistantError, match=error):
#         await hass.services.async_call(
#             DOMAIN,
#             service,
#             {ATTR_DEVICE_ID: device.id, ATTR_PROGRAM_ID: 1},
#             blocking=True,
#         )
#     mock_myuplink_client.set_program.assert_called_once_with(
#         TEST_APPLIANCE, {"programId": 1}
#     )


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
            SERVICE_SET_DATAPOINT,
            {ATTR_DEVICE_ID: device.id, ATTR_DATAPOINT_ID: 12345, ATTR_VALUE: "test"},
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
            SERVICE_SET_DATAPOINT,
            {ATTR_DEVICE_ID: device.id},
            blocking=True,
        )
    mock_myuplink_client.async_set_device_points.assert_not_called()

    # Test invalid device
    with pytest.raises(ServiceValidationError, match="Invalid device targeted"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DATAPOINT,
            {
                ATTR_DEVICE_ID: "invalid_device",
                ATTR_DATAPOINT_ID: 12345,
                ATTR_VALUE: "test",
            },
            blocking=True,
        )
    mock_myuplink_client.async_set_device_points.assert_not_called()
