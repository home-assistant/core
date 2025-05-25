"""Tests the services provided by the miele integration."""

from unittest.mock import MagicMock

from aiohttp import ClientResponseError
import pytest
from voluptuous import MultipleInvalid

from homeassistant.components.miele.const import DOMAIN
from homeassistant.const import CONF_DEVICE_ID
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
        "set_program",
        {
            CONF_DEVICE_ID: device.id,
            "program_id": 24,
        },
        blocking=True,
    )
    mock_miele_client.set_program.assert_called_once_with(
        TEST_APPLIANCE, {"programId": 24}
    )
    mock_miele_client.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "set_program",
        {
            CONF_DEVICE_ID: device.id,
            "program_id": 24,
            "duration": 75,
            "temperature": 195,
        },
        blocking=True,
    )
    mock_miele_client.set_program.assert_called_once_with(
        TEST_APPLIANCE, {"programId": 24, "duration": [1, 15], "temperature": 195}
    )
    mock_miele_client.reset_mock()


async def test_service_api_errors(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service api errors."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_APPLIANCE)})

    # Test http error
    mock_miele_client.set_program.side_effect = ClientResponseError("TestInfo", "test")
    with pytest.raises(HomeAssistantError, match="'Set program' action failed"):
        await hass.services.async_call(
            DOMAIN,
            "set_program",
            {"device_id": device.id, "program_id": 1},
            blocking=True,
        )
    mock_miele_client.set_program.assert_called_once_with(
        TEST_APPLIANCE, {"programId": 1}
    )


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
            "set_program",
            {"device_id": device.id},
            blocking=True,
        )
    mock_miele_client.set_program.assert_not_called()

    # Test invalid program_id
    with pytest.raises(MultipleInvalid, match="expected int for dictionary value"):
        await hass.services.async_call(
            DOMAIN,
            "set_program",
            {"device_id": device.id, "program_id": "invalid"},
            blocking=True,
        )
    mock_miele_client.set_program.assert_not_called()

    # Test invalid device
    with pytest.raises(
        ServiceValidationError, match="'Set program' action failed: No device"
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_program",
            {"device_id": "invalid_device", "program_id": 1},
            blocking=True,
        )
    mock_miele_client.set_program.assert_not_called()
