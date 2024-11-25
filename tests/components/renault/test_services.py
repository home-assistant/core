"""Tests for Renault sensors."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import patch

import pytest
from renault_api.exceptions import RenaultException
from renault_api.kamereon import schemas
from renault_api.kamereon.models import ChargeSchedule, HvacSchedule
from syrupy import SnapshotAssertion

from homeassistant.components.renault.const import DOMAIN
from homeassistant.components.renault.services import (
    ATTR_SCHEDULES,
    ATTR_TEMPERATURE,
    ATTR_VEHICLE,
    ATTR_WHEN,
    SERVICE_AC_CANCEL,
    SERVICE_AC_SET_SCHEDULES,
    SERVICE_AC_START,
    SERVICE_CHARGE_SET_SCHEDULES,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_MODEL_ID,
    ATTR_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import MOCK_VEHICLES

from tests.common import load_fixture

pytestmark = pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.renault.PLATFORMS", []):
        yield


@pytest.fixture(autouse=True, name="vehicle_type", params=["zoe_40"])
def override_vehicle_type(request: pytest.FixtureRequest) -> str:
    """Parametrize vehicle type."""
    return request.param


def get_device_id(hass: HomeAssistant) -> str:
    """Get device_id."""
    device_registry = dr.async_get(hass)
    identifiers = {(DOMAIN, "VF1AAAAA555777999")}
    device = device_registry.async_get_device(identifiers=identifiers)
    return device.id


async def test_service_set_ac_cancel(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test that service invokes renault_api with correct data."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    data = {
        ATTR_VEHICLE: get_device_id(hass),
    }

    with (
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.set_ac_stop",
            side_effect=RenaultException("Didn't work"),
        ) as mock_action,
        pytest.raises(HomeAssistantError, match="Didn't work"),
    ):
        await hass.services.async_call(
            DOMAIN, SERVICE_AC_CANCEL, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    assert mock_action.mock_calls[0][1] == ()


async def test_service_set_ac_start_simple(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test that service invokes renault_api with correct data."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

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


async def test_service_set_ac_start_with_date(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test that service invokes renault_api with correct data."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

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


async def test_service_set_charge_schedule(
    hass: HomeAssistant, config_entry: ConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test that service invokes renault_api with correct data."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    schedules = {"id": 2}
    data = {
        ATTR_VEHICLE: get_device_id(hass),
        ATTR_SCHEDULES: schedules,
    }

    with (
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.get_charging_settings",
            return_value=schemas.KamereonVehicleDataResponseSchema.loads(
                load_fixture("renault/charging_settings.json")
            ).get_attributes(schemas.KamereonVehicleChargingSettingsDataSchema),
        ),
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.set_charge_schedules",
            return_value=(
                schemas.KamereonVehicleHvacStartActionDataSchema.loads(
                    load_fixture("renault/action.set_charge_schedules.json")
                )
            ),
        ) as mock_action,
    ):
        await hass.services.async_call(
            DOMAIN, SERVICE_CHARGE_SET_SCHEDULES, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    mock_call_data: list[ChargeSchedule] = mock_action.mock_calls[0][1][0]
    assert mock_call_data == snapshot


async def test_service_set_charge_schedule_multi(
    hass: HomeAssistant, config_entry: ConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test that service invokes renault_api with correct data."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    schedules = [
        {
            "id": 2,
            "activated": True,
            "monday": {"startTime": "T12:00Z", "duration": 30},
            "tuesday": {"startTime": "T12:00Z", "duration": 30},
            "wednesday": None,
            "friday": {"startTime": "T12:00Z", "duration": 30},
            "saturday": {"startTime": "T12:00Z", "duration": 30},
            "sunday": {"startTime": "T12:00Z", "duration": 30},
        },
        {"id": 3},
    ]
    data = {
        ATTR_VEHICLE: get_device_id(hass),
        ATTR_SCHEDULES: schedules,
    }

    with (
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.get_charging_settings",
            return_value=schemas.KamereonVehicleDataResponseSchema.loads(
                load_fixture("renault/charging_settings.json")
            ).get_attributes(schemas.KamereonVehicleChargingSettingsDataSchema),
        ),
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.set_charge_schedules",
            return_value=(
                schemas.KamereonVehicleHvacStartActionDataSchema.loads(
                    load_fixture("renault/action.set_charge_schedules.json")
                )
            ),
        ) as mock_action,
    ):
        await hass.services.async_call(
            DOMAIN, SERVICE_CHARGE_SET_SCHEDULES, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    mock_call_data: list[ChargeSchedule] = mock_action.mock_calls[0][1][0]
    assert mock_call_data == snapshot

    # Monday updated with new values
    assert mock_call_data[1].monday.startTime == "T12:00Z"
    assert mock_call_data[1].monday.duration == 30
    # Wednesday has original values cleared
    assert mock_call_data[1].wednesday is None
    # Thursday keeps original values
    assert mock_call_data[1].thursday.startTime == "T23:30Z"
    assert mock_call_data[1].thursday.duration == 15


async def test_service_set_ac_schedule(
    hass: HomeAssistant, config_entry: ConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test that service invokes renault_api with correct data."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    schedules = {"id": 2}
    data = {
        ATTR_VEHICLE: get_device_id(hass),
        ATTR_SCHEDULES: schedules,
    }

    with (
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.get_hvac_settings",
            return_value=schemas.KamereonVehicleDataResponseSchema.loads(
                load_fixture("renault/hvac_settings.json")
            ).get_attributes(schemas.KamereonVehicleHvacSettingsDataSchema),
        ),
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.set_hvac_schedules",
            return_value=(
                schemas.KamereonVehicleHvacScheduleActionDataSchema.loads(
                    load_fixture("renault/action.set_ac_schedules.json")
                )
            ),
        ) as mock_action,
    ):
        await hass.services.async_call(
            DOMAIN, SERVICE_AC_SET_SCHEDULES, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    mock_call_data: list[ChargeSchedule] = mock_action.mock_calls[0][1][0]
    assert mock_call_data == snapshot


async def test_service_set_ac_schedule_multi(
    hass: HomeAssistant, config_entry: ConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test that service invokes renault_api with correct data."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    schedules = [
        {
            "id": 3,
            "activated": True,
            "monday": {"readyAtTime": "T12:00Z"},
            "tuesday": {"readyAtTime": "T12:00Z"},
            "wednesday": None,
            "friday": {"readyAtTime": "T12:00Z"},
            "saturday": {"readyAtTime": "T12:00Z"},
            "sunday": {"readyAtTime": "T12:00Z"},
        },
        {"id": 4},
    ]
    data = {
        ATTR_VEHICLE: get_device_id(hass),
        ATTR_SCHEDULES: schedules,
    }

    with (
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.get_hvac_settings",
            return_value=schemas.KamereonVehicleDataResponseSchema.loads(
                load_fixture("renault/hvac_settings.json")
            ).get_attributes(schemas.KamereonVehicleHvacSettingsDataSchema),
        ),
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.set_hvac_schedules",
            return_value=(
                schemas.KamereonVehicleHvacScheduleActionDataSchema.loads(
                    load_fixture("renault/action.set_ac_schedules.json")
                )
            ),
        ) as mock_action,
    ):
        await hass.services.async_call(
            DOMAIN, SERVICE_AC_SET_SCHEDULES, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    mock_call_data: list[HvacSchedule] = mock_action.mock_calls[0][1][0]
    assert mock_call_data == snapshot

    # Schedule is activated now
    assert mock_call_data[2].activated is True
    # Monday updated with new values
    assert mock_call_data[2].monday.readyAtTime == "T12:00Z"
    # Wednesday has original values cleared
    assert mock_call_data[2].wednesday is None
    # Thursday keeps original values
    assert mock_call_data[2].thursday.readyAtTime == "T23:30Z"


async def test_service_invalid_device_id(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test that service fails with ValueError if device_id not found in registry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    data = {ATTR_VEHICLE: "some_random_id"}

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, SERVICE_AC_CANCEL, service_data=data, blocking=True
        )
    assert err.value.translation_key == "invalid_device_id"
    assert err.value.translation_placeholders == {"device_id": "some_random_id"}


async def test_service_invalid_device_id2(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, config_entry: ConfigEntry
) -> None:
    """Test that service fails with ValueError if device_id not found in vehicles."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    extra_vehicle = MOCK_VEHICLES["captur_phev"]["expected_device"]

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers=extra_vehicle[ATTR_IDENTIFIERS],
        manufacturer=extra_vehicle[ATTR_MANUFACTURER],
        name=extra_vehicle[ATTR_NAME],
        model=extra_vehicle[ATTR_MODEL],
        model_id=extra_vehicle[ATTR_MODEL_ID],
    )
    device_id = device_registry.async_get_device(
        identifiers=extra_vehicle[ATTR_IDENTIFIERS]
    ).id

    data = {ATTR_VEHICLE: device_id}

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, SERVICE_AC_CANCEL, service_data=data, blocking=True
        )
    assert err.value.translation_key == "no_config_entry_for_device"
    assert err.value.translation_placeholders == {"device_id": "REG-NUMBER"}
