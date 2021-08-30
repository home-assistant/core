"""Tests for Renault sensors."""
from datetime import datetime
from unittest.mock import patch

import pytest
from renault_api.kamereon import schemas
from renault_api.kamereon.models import ChargeSchedule

from homeassistant.components.renault.const import DOMAIN
from homeassistant.components.renault.services import (
    ATTR_CHARGE_MODE,
    ATTR_SCHEDULES,
    ATTR_TEMPERATURE,
    ATTR_VIN,
    ATTR_WHEN,
    SERVICE_AC_CANCEL,
    SERVICE_AC_START,
    SERVICE_CHARGE_SET_MODE,
    SERVICE_CHARGE_SET_SCHEDULES,
    SERVICE_CHARGE_START,
    SERVICES,
)
from homeassistant.core import HomeAssistant

from . import setup_renault_integration_simple, setup_renault_integration_vehicle

from tests.common import load_fixture

MOCK_VIN = "VF1AAAAA555777999"


async def test_service_registration(hass: HomeAssistant):
    """Test entry setup and unload."""
    with patch("homeassistant.components.renault.PLATFORMS", []):
        config_entry = await setup_renault_integration_simple(hass)

    # Check that all services are registered.
    for service in SERVICES:
        assert hass.services.has_service(DOMAIN, service)

    # Unload the entry
    await hass.config_entries.async_unload(config_entry.entry_id)

    # Check that all services are un-registered.
    for service in SERVICES:
        assert not hass.services.has_service(DOMAIN, service)


async def test_service_set_ac_cancel(hass: HomeAssistant):
    """Test that service invokes renault_api with correct data."""
    await setup_renault_integration_vehicle(hass, "zoe_40")

    data = {
        ATTR_VIN: MOCK_VIN,
    }

    with patch(
        "renault_api.renault_vehicle.RenaultVehicle.set_ac_stop",
        return_value=(
            schemas.KamereonVehicleHvacStartActionDataSchema.loads(
                load_fixture("renault/action.set_ac_stop.json")
            )
        ),
    ) as mock_action:
        await hass.services.async_call(
            DOMAIN, SERVICE_AC_CANCEL, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    assert mock_action.mock_calls[0][1] == ()


async def test_service_set_ac_start_simple(hass: HomeAssistant):
    """Test that service invokes renault_api with correct data."""
    await setup_renault_integration_vehicle(hass, "zoe_40")

    temperature = 13.5
    data = {
        ATTR_VIN: MOCK_VIN,
        ATTR_TEMPERATURE: temperature,
    }

    with patch(
        "renault_api.renault_vehicle.RenaultVehicle.set_ac_start",
        return_value=(
            schemas.KamereonVehicleHvacStartActionDataSchema.loads(
                load_fixture("renault/action.set_ac_start.json")
            )
        ),
    ) as mock_action:
        await hass.services.async_call(
            DOMAIN, SERVICE_AC_START, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    assert mock_action.mock_calls[0][1] == (temperature, None)


async def test_service_set_ac_start_with_date(hass: HomeAssistant):
    """Test that service invokes renault_api with correct data."""
    await setup_renault_integration_vehicle(hass, "zoe_40")

    temperature = 13.5
    when = datetime(2025, 8, 23, 17, 12, 45)
    data = {
        ATTR_VIN: MOCK_VIN,
        ATTR_TEMPERATURE: temperature,
        ATTR_WHEN: when,
    }

    with patch(
        "renault_api.renault_vehicle.RenaultVehicle.set_ac_start",
        return_value=(
            schemas.KamereonVehicleHvacStartActionDataSchema.loads(
                load_fixture("renault/action.set_ac_start.json")
            )
        ),
    ) as mock_action:
        await hass.services.async_call(
            DOMAIN, SERVICE_AC_START, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    assert mock_action.mock_calls[0][1] == (temperature, when)


async def test_service_set_charge_mode(hass: HomeAssistant):
    """Test that service invokes renault_api with correct data."""
    await setup_renault_integration_vehicle(hass, "zoe_40")

    mode = "always"
    data = {
        ATTR_VIN: MOCK_VIN,
        ATTR_CHARGE_MODE: mode,
    }

    with patch(
        "renault_api.renault_vehicle.RenaultVehicle.set_charge_mode",
        return_value=(
            schemas.KamereonVehicleHvacStartActionDataSchema.loads(
                load_fixture("renault/action.set_charge_mode.json")
            )
        ),
    ) as mock_action:
        await hass.services.async_call(
            DOMAIN, SERVICE_CHARGE_SET_MODE, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    assert mock_action.mock_calls[0][1] == (mode,)


async def test_service_set_charge_schedule(hass: HomeAssistant):
    """Test that service invokes renault_api with correct data."""
    await setup_renault_integration_vehicle(hass, "zoe_40")

    schedules = {"id": 2}
    data = {
        ATTR_VIN: MOCK_VIN,
        ATTR_SCHEDULES: schedules,
    }

    with patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_charging_settings",
        return_value=schemas.KamereonVehicleDataResponseSchema.loads(
            load_fixture("renault/charging_settings.json")
        ).get_attributes(schemas.KamereonVehicleChargingSettingsDataSchema),
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.set_charge_schedules",
        return_value=(
            schemas.KamereonVehicleHvacStartActionDataSchema.loads(
                load_fixture("renault/action.set_charge_schedules.json")
            )
        ),
    ) as mock_action:
        await hass.services.async_call(
            DOMAIN, SERVICE_CHARGE_SET_SCHEDULES, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    mock_call_data: list[ChargeSchedule] = mock_action.mock_calls[0][1][0]
    assert mock_action.mock_calls[0][1] == (mock_call_data,)


async def test_service_set_charge_schedule_multi(hass: HomeAssistant):
    """Test that service invokes renault_api with correct data."""
    await setup_renault_integration_vehicle(hass, "zoe_40")

    schedules = [
        {
            "id": 2,
            "activated": True,
            "monday": {"startTime": "T12:00Z", "duration": 15},
            "tuesday": {"startTime": "T12:00Z", "duration": 15},
            "wednesday": {"startTime": "T12:00Z", "duration": 15},
            "thursday": {"startTime": "T12:00Z", "duration": 15},
            "friday": {"startTime": "T12:00Z", "duration": 15},
            "saturday": {"startTime": "T12:00Z", "duration": 15},
            "sunday": {"startTime": "T12:00Z", "duration": 15},
        },
        {"id": 3},
    ]
    data = {
        ATTR_VIN: MOCK_VIN,
        ATTR_SCHEDULES: schedules,
    }

    with patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_charging_settings",
        return_value=schemas.KamereonVehicleDataResponseSchema.loads(
            load_fixture("renault/charging_settings.json")
        ).get_attributes(schemas.KamereonVehicleChargingSettingsDataSchema),
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.set_charge_schedules",
        return_value=(
            schemas.KamereonVehicleHvacStartActionDataSchema.loads(
                load_fixture("renault/action.set_charge_schedules.json")
            )
        ),
    ) as mock_action:
        await hass.services.async_call(
            DOMAIN, SERVICE_CHARGE_SET_SCHEDULES, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    mock_call_data: list[ChargeSchedule] = mock_action.mock_calls[0][1][0]
    assert mock_action.mock_calls[0][1] == (mock_call_data,)


async def test_service_set_charge_start(hass: HomeAssistant):
    """Test that service invokes renault_api with correct data."""
    await setup_renault_integration_vehicle(hass, "zoe_40")

    data = {
        ATTR_VIN: MOCK_VIN,
    }

    with patch(
        "renault_api.renault_vehicle.RenaultVehicle.set_charge_start",
        return_value=(
            schemas.KamereonVehicleHvacStartActionDataSchema.loads(
                load_fixture("renault/action.set_charge_start.json")
            )
        ),
    ) as mock_action:
        await hass.services.async_call(
            DOMAIN, SERVICE_CHARGE_START, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    assert mock_action.mock_calls[0][1] == ()


async def test_service_invalid_vin(hass: HomeAssistant):
    """Test that service fails with ValueError if VIN is not available."""
    await setup_renault_integration_vehicle(hass, "zoe_40")

    data = {
        ATTR_VIN: MOCK_VIN.replace("A", "B"),
    }

    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN, SERVICE_AC_CANCEL, service_data=data, blocking=True
        )
