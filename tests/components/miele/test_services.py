"""Tests the services provided by the miele integration."""

from datetime import timedelta
from unittest.mock import MagicMock

from aiohttp import ClientResponseError
import pytest
from syrupy.assertion import SnapshotAssertion
from voluptuous import MultipleInvalid

from homeassistant.components.miele.const import DOMAIN
from homeassistant.components.miele.services import (
    ATTR_DURATION,
    ATTR_PROGRAM_ID,
    SERVICE_GET_PROGRAMS,
    SERVICE_SET_PROGRAM,
    SERVICE_SET_PROGRAM_OVEN,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceRegistry

from . import setup_integration

from tests.common import MockConfigEntry

TEST_APPLIANCE = "Dummy_Appliance_1"


async def test_services(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Tests that the custom services are correct."""

    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_APPLIANCE)})
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PROGRAM,
        {
            ATTR_DEVICE_ID: device.id,
            ATTR_PROGRAM_ID: 24,
        },
        blocking=True,
    )
    mock_miele_client.set_program.assert_called_once_with(
        TEST_APPLIANCE, {"programId": 24}
    )


@pytest.mark.parametrize(
    ("call_arguments", "miele_arguments"),
    [
        (
            {ATTR_PROGRAM_ID: 24},
            {"programId": 24},
        ),
        (
            {ATTR_PROGRAM_ID: 25, ATTR_DURATION: timedelta(minutes=75)},
            {"programId": 25, "duration": [1, 15]},
        ),
        (
            {
                ATTR_PROGRAM_ID: 26,
                ATTR_DURATION: timedelta(minutes=135),
                ATTR_TEMPERATURE: 180,
            },
            {"programId": 26, "duration": [2, 15], "temperature": 180},
        ),
    ],
)
async def test_services_oven(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    call_arguments: dict,
    miele_arguments: dict,
) -> None:
    """Tests that the custom services are correct for ovens."""

    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_APPLIANCE)})
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PROGRAM_OVEN,
        {ATTR_DEVICE_ID: device.id, **call_arguments},
        blocking=True,
    )
    mock_miele_client.set_program.assert_called_once_with(
        TEST_APPLIANCE, miele_arguments
    )


async def test_services_with_response(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests that the custom services that returns a response are correct."""

    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_APPLIANCE)})
    assert snapshot == await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PROGRAMS,
        {
            ATTR_DEVICE_ID: device.id,
        },
        blocking=True,
        return_response=True,
    )


@pytest.mark.parametrize(
    ("service", "error"),
    [
        (SERVICE_SET_PROGRAM, "'Set program' action failed"),
        (SERVICE_SET_PROGRAM_OVEN, "'Set program on oven' action failed"),
    ],
)
async def test_service_api_errors(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    error: str,
) -> None:
    """Test service api errors."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_APPLIANCE)})

    # Test http error
    mock_miele_client.set_program.side_effect = ClientResponseError("TestInfo", "test")
    with pytest.raises(HomeAssistantError, match=error):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_DEVICE_ID: device.id, ATTR_PROGRAM_ID: 1},
            blocking=True,
        )
    mock_miele_client.set_program.assert_called_once_with(
        TEST_APPLIANCE, {"programId": 1}
    )


async def test_get_service_api_errors(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service api errors."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_APPLIANCE)})

    # Test http error
    mock_miele_client.get_programs.side_effect = ClientResponseError("TestInfo", "test")
    with pytest.raises(HomeAssistantError, match="'Get programs' action failed"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PROGRAMS,
            {ATTR_DEVICE_ID: device.id},
            blocking=True,
            return_response=True,
        )
    mock_miele_client.get_programs.assert_called_once()


async def test_service_validation_errors(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Tests that the custom services handle bad data."""

    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_APPLIANCE)})

    # Test missing program_id
    with pytest.raises(MultipleInvalid, match="required key not provided"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PROGRAM,
            {"device_id": device.id},
            blocking=True,
        )
    mock_miele_client.set_program.assert_not_called()

    # Test invalid program_id
    with pytest.raises(MultipleInvalid, match="expected int for dictionary value"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PROGRAM,
            {"device_id": device.id, ATTR_PROGRAM_ID: "invalid"},
            blocking=True,
        )
    mock_miele_client.set_program.assert_not_called()

    # Test invalid device
    with pytest.raises(ServiceValidationError, match="Invalid device targeted"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PROGRAM,
            {"device_id": "invalid_device", ATTR_PROGRAM_ID: 1},
            blocking=True,
        )
    mock_miele_client.set_program.assert_not_called()
