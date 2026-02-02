"""Tests for Tuya services."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.tuya.const import DOMAIN
from homeassistant.components.tuya.service import async_register_services
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from . import initialize_entry

from tests.common import MockConfigEntry


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
async def test_get_data_success(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test get_meal_plan_data service returns device status."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await async_register_services(hass)

    with patch(
        "homeassistant.components.tuya.service._get_tuya_device",
        return_value=(mock_device, mock_manager),
    ):
        result = await hass.services.async_call(
            DOMAIN,
            "get_meal_plan_data",
            {"device_id": mock_device.id},
            blocking=True,
            return_response=True,
        )
    assert result["data"] == mock_device.status["meal_plan"]


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
async def test_set_data_success(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test set_meal_plan_data service sends command."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await async_register_services(hass)

    with patch(
        "homeassistant.components.tuya.service._get_tuya_device",
        return_value=(mock_device, mock_manager),
    ):
        result = await hass.services.async_call(
            DOMAIN,
            "set_meal_plan_data",
            {
                "device_id": mock_device.id,
                "data": "fwQAAgB/BgABAH8JAAIBfwwAAQB/DwACAX8VAAIBfxcAAQAIEgABAQ==",
            },
            blocking=True,
            return_response=True,
        )

    assert result["success"] is True
    assert result["value"] == "fwQAAgB/BgABAH8JAAIBfwwAAQB/DwACAX8VAAIBfxcAAQAIEgABAQ=="
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [
            {
                "code": "meal_plan",
                "value": "fwQAAgB/BgABAH8JAAIBfwwAAQB/DwACAX8VAAIBfxcAAQAIEgABAQ==",
            }
        ],
    )


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
@pytest.mark.parametrize(
    "data_value",
    [
        "string_value",
    ],
)
async def test_set_data_various_data_types(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    data_value,
) -> None:
    """Test set_data service with various data types."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await async_register_services(hass)

    with patch(
        "homeassistant.components.tuya.service._get_tuya_device",
        return_value=(mock_device, mock_manager),
    ):
        result = await hass.services.async_call(
            DOMAIN,
            "set_meal_plan_data",
            {"device_id": mock_device.id, "data": data_value},
            blocking=True,
            return_response=True,
        )

    assert result["value"] == data_value


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
async def test_services_with_actual_device_lookup(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test services with actual _get_tuya_device implementation."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await async_register_services(hass)

    # Get the device ID from the device registry
    device_registry = dr.async_get(hass)
    device = list(device_registry.devices.values())[0]

    # Test get_data
    result = await hass.services.async_call(
        DOMAIN,
        "get_meal_plan_data",
        {"device_id": device.id},
        blocking=True,
        return_response=True,
    )
    assert result["data"] == mock_device.status["meal_plan"]

    # Test set_data
    result = await hass.services.async_call(
        DOMAIN,
        "set_meal_plan_data",
        {
            "device_id": device.id,
            "data": "fwQAAgB/BgABAH8JAAIBfwwAAQB/DwACAX8VAAIBfxcAAQAIEgABAQ==",
        },
        blocking=True,
        return_response=True,
    )
    assert result["success"] is True
    mock_manager.send_commands.assert_called_once()


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
async def test_get_tuya_device_error_cases(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test _get_tuya_device error handling paths."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await async_register_services(hass)

    with pytest.raises(HomeAssistantError, match="Device .* not found"):
        await hass.services.async_call(
            DOMAIN,
            "get_meal_plan_data",
            {"device_id": "invalid_device_id"},
            blocking=True,
            return_response=True,
        )

    # Test: device is not a Tuya device
    device_registry = dr.async_get(hass)
    non_tuya_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("other_domain", "some_id")},
        name="Non-Tuya Device",
    )
    with pytest.raises(HomeAssistantError, match="is not a Tuya device"):
        await hass.services.async_call(
            DOMAIN,
            "get_meal_plan_data",
            {"device_id": non_tuya_device.id},
            blocking=True,
            return_response=True,
        )

    # Test: Tuya device not in config entry
    tuya_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "unknown_tuya_id")},
        name="Unknown Tuya Device",
    )
    with pytest.raises(HomeAssistantError, match="Tuya device .* not found"):
        await hass.services.async_call(
            DOMAIN,
            "get_meal_plan_data",
            {"device_id": tuya_device.id},
            blocking=True,
            return_response=True,
        )
