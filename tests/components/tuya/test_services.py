"""Tests for Tuya services."""

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_device_handlers.device_wrapper.service_feeder_schedule import FeederSchedule
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.tuya.const import DOMAIN
from homeassistant.components.tuya.services import Service
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import initialize_entry

from tests.common import MockConfigEntry

DECODED_MEAL_PLAN: list[FeederSchedule] = [
    {
        "days": [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ],
        "time": "09:00",
        "portion": 1,
        "enabled": True,
    },
    {
        "days": [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ],
        "time": "09:30",
        "portion": 1,
        "enabled": True,
    },
]


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
async def test_get_feeder_meal_plan(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test GET_FEEDER_MEAL_PLAN with valid meal plan data."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_device.id)}
    )
    assert device_entry is not None
    device_id = device_entry.id

    result = await hass.services.async_call(
        DOMAIN,
        Service.GET_FEEDER_MEAL_PLAN,
        {"device_id": device_id},
        blocking=True,
        return_response=True,
    )
    assert result == snapshot


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
async def test_get_feeder_meal_plan_invalid_meal_plan(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test GET_FEEDER_MEAL_PLAN error when meal plan data is missing."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_device.id)}
    )
    assert device_entry is not None
    device_id = device_entry.id

    mock_device.status.pop("meal_plan", None)
    with pytest.raises(
        HomeAssistantError,
        match="Unable to parse meal plan data",
    ):
        await hass.services.async_call(
            DOMAIN,
            Service.GET_FEEDER_MEAL_PLAN,
            {"device_id": device_id},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
async def test_set_feeder_meal_plan(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test SET_FEEDER_MEAL_PLAN with valid device and meal plan data."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_device.id)}
    )
    assert device_entry is not None
    device_id = device_entry.id

    await hass.services.async_call(
        DOMAIN,
        Service.SET_FEEDER_MEAL_PLAN,
        {
            "device_id": device_id,
            "meal_plan": DECODED_MEAL_PLAN,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [{"code": "meal_plan", "value": "fwkAAQF/CR4BAQ=="}],
    )


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
async def test_set_feeder_meal_plan_unsupported_device(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test SET_FEEDER_MEAL_PLAN error when device is unsupported."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_device.id)}
    )
    assert device_entry is not None
    device_id = device_entry.id

    mock_device.product_id = "unsupported_product"
    with pytest.raises(
        ServiceValidationError,
        match=f"Feeder with ID {mock_device.id} does not support meal plan functionality",
    ):
        await hass.services.async_call(
            DOMAIN,
            Service.SET_FEEDER_MEAL_PLAN,
            {
                "device_id": device_id,
                "meal_plan": DECODED_MEAL_PLAN,
            },
            blocking=True,
        )


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
async def test_get_tuya_device_error_device_not_found(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test service error when device ID does not exist."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    with pytest.raises(
        ServiceValidationError,
        match="Feeder with ID invalid_device_id could not be found",
    ):
        await hass.services.async_call(
            DOMAIN,
            Service.GET_FEEDER_MEAL_PLAN,
            {"device_id": "invalid_device_id"},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
async def test_get_tuya_device_error_non_tuya_device(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test service error when target device is not a Tuya device."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    device_registry = dr.async_get(hass)
    non_tuya_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("other_domain", "some_id")},
        name="Non-Tuya Device",
    )
    with pytest.raises(
        ServiceValidationError,
        match=f"Device with ID {non_tuya_device.id} is not a Tuya feeder",
    ):
        await hass.services.async_call(
            DOMAIN,
            Service.GET_FEEDER_MEAL_PLAN,
            {"device_id": non_tuya_device.id},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("mock_device_code", ["cwwsq_wfkzyy0evslzsmoi"])
async def test_get_tuya_device_error_unknown_tuya_device(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test service error when Tuya identifier is not present in manager map."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    device_registry = dr.async_get(hass)
    tuya_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "unknown_tuya_id")},
        name="Unknown Tuya Device",
    )
    with pytest.raises(
        ServiceValidationError,
        match=f"Feeder with ID {tuya_device.id} could not be found",
    ):
        await hass.services.async_call(
            DOMAIN,
            Service.GET_FEEDER_MEAL_PLAN,
            {"device_id": tuya_device.id},
            blocking=True,
            return_response=True,
        )
