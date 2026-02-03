"""Tests for Tuya services."""

from __future__ import annotations

from typing import Any

import pytest
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.tuya.const import DOMAIN
from homeassistant.components.tuya.services import Service, _get_tuya_device
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import initialize_entry

from tests.common import MockConfigEntry


def find_device_id(mock_device: CustomerDevice, hass: HomeAssistant) -> str:
    """Helper to find the Home Assistant device registry ID for a mock Tuya device."""
    tuya_device_id = mock_device.id
    device_registry = dr.async_get(hass)

    for entry in device_registry.devices.values():
        if (DOMAIN, tuya_device_id) in entry.identifiers:
            return entry.id

    raise ValueError(f"Device with Tuya ID {tuya_device_id} not found in registry")


def decoded_meal_plan() -> list[dict[str, Any]]:
    """Return raw meal plan data for testing."""
    return [
        {
            "days": [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ],
            "hour": 9,
            "minute": 0,
            "portion": 1,
            "enabled": 1,
        },
        {
            "days": [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ],
            "hour": 9,
            "minute": 30,
            "portion": 1,
            "enabled": 1,
        },
        {
            "days": [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ],
            "hour": 12,
            "minute": 0,
            "portion": 1,
            "enabled": 1,
        },
        {
            "days": [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ],
            "hour": 15,
            "minute": 0,
            "portion": 2,
            "enabled": 1,
        },
        {
            "days": [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ],
            "hour": 21,
            "minute": 0,
            "portion": 2,
            "enabled": 1,
        },
    ]


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
async def test_get_meal_plan_data(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test GET_MEAL_PLAN_DATA normal and error cases using real device registry."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    device_id = find_device_id(mock_device, hass)

    # Normal case
    result = await hass.services.async_call(
        DOMAIN,
        Service.GET_MEAL_PLAN_DATA,
        {"device_id": device_id},
        blocking=True,
        return_response=True,
    )
    assert result["data"] == decoded_meal_plan()

    # Error case: no meal_plan in device status
    mock_device.status.pop("meal_plan", None)
    with pytest.raises(
        ServiceValidationError,
        match="Feeder with ID iomszlsve0yyzkfwqswwc does not support meal plan status",
    ):
        await hass.services.async_call(
            DOMAIN,
            Service.GET_MEAL_PLAN_DATA,
            {"device_id": device_id},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
async def test_set_meal_plan_data(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test SET_MEAL_PLAN_DATA normal and error cases using real device registry."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    device_id = find_device_id(mock_device, hass)

    # Normal case
    await hass.services.async_call(
        DOMAIN,
        Service.SET_MEAL_PLAN_DATA,
        {
            "device_id": device_id,
            "data": decoded_meal_plan(),
        },
        blocking=True,
    )
    # We use mock_device.id since this is sent to the manager
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [{"code": "meal_plan", "value": mock_device.status["meal_plan"]}],
    )

    # Error case: unsupported meal_plan function
    mock_device.function = []
    with pytest.raises(
        ServiceValidationError,
        match="Feeder with ID iomszlsve0yyzkfwqswwc does not support meal plan functionality",
    ):
        await hass.services.async_call(
            DOMAIN,
            Service.SET_MEAL_PLAN_DATA,
            {
                "device_id": device_id,
                "data": decoded_meal_plan(),
            },
            blocking=True,
        )


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
async def test_get_tuya_device_error_cases(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test _get_tuya_device error handling paths."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Case 1: Device ID not found
    with pytest.raises(
        ServiceValidationError, match="Feeder with ID .+? could not be found"
    ):
        _get_tuya_device(hass, "invalid_device_id")

    # Case 2: Device exists but is not a Tuya device
    device_registry = dr.async_get(hass)
    non_tuya_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("other_domain", "some_id")},
        name="Non-Tuya Device",
    )
    with pytest.raises(
        ServiceValidationError, match="Device with ID .+? is not a Tuya feeder"
    ):
        _get_tuya_device(hass, non_tuya_device.id)

    # Case 3: Tuya device exists in registry but not in manager.device_map
    tuya_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "unknown_tuya_id")},
        name="Unknown Tuya Device",
    )
    with pytest.raises(
        ServiceValidationError, match="Feeder with ID .+? could not be found"
    ):
        _get_tuya_device(hass, tuya_device.id)
