"""Tests for Renault sensors."""
from datetime import datetime
from unittest.mock import patch

import pytest
from renault_api.kamereon import schemas
from renault_api.kamereon.models import ChargeSchedule

from homeassistant.components.renault.const import DOMAIN
from homeassistant.components.renault.services import (
    ATTR_SCHEDULES,
    ATTR_TEMPERATURE,
    ATTR_VEHICLE,
    ATTR_WHEN,
    SERVICE_AC_CANCEL,
    SERVICE_AC_START,
    SERVICE_CHARGE_SET_SCHEDULES,
    SERVICE_CHARGE_START,
    SERVICES,
)
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_renault_integration_simple, setup_renault_integration_vehicle

from tests.common import load_fixture
from tests.components.renault.const import MOCK_VEHICLES


def get_device_id(hass: HomeAssistant) -> str:
    """Get device_id."""
    device_registry = dr.async_get(hass)
    identifiers = {(DOMAIN, "VF1AAAAA555777999")}
    device = device_registry.async_get_device(identifiers)
    return device.id


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
        ATTR_VEHICLE: get_device_id(hass),
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
        ATTR_VEHICLE: get_device_id(hass),
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
        ATTR_VEHICLE: get_device_id(hass),
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


async def test_service_set_charge_schedule(hass: HomeAssistant):
    """Test that service invokes renault_api with correct data."""
    await setup_renault_integration_vehicle(hass, "zoe_40")

    schedules = {"id": 2}
    data = {
        ATTR_VEHICLE: get_device_id(hass),
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
        ATTR_VEHICLE: get_device_id(hass),
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
        ATTR_VEHICLE: get_device_id(hass),
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


async def test_service_invalid_device_id(hass: HomeAssistant):
    """Test that service fails with ValueError if device_id not found in registry."""
    await setup_renault_integration_vehicle(hass, "zoe_40")

    data = {ATTR_VEHICLE: "VF1AAAAA555777999"}

    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN, SERVICE_AC_CANCEL, service_data=data, blocking=True
        )


async def test_service_invalid_device_id2(hass: HomeAssistant):
    """Test that service fails with ValueError if device_id not found in vehicles."""
    config_entry = await setup_renault_integration_vehicle(hass, "zoe_40")

    extra_vehicle = MOCK_VEHICLES["captur_phev"]["expected_device"]

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers=extra_vehicle[ATTR_IDENTIFIERS],
        manufacturer=extra_vehicle[ATTR_MANUFACTURER],
        name=extra_vehicle[ATTR_NAME],
        model=extra_vehicle[ATTR_MODEL],
        sw_version=extra_vehicle[ATTR_SW_VERSION],
    )
    device_id = device_registry.async_get_device(extra_vehicle[ATTR_IDENTIFIERS]).id

    data = {ATTR_VEHICLE: device_id}

    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN, SERVICE_AC_CANCEL, service_data=data, blocking=True
        )
