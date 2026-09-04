"""Test the Tesla Fleet services."""

from datetime import time
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.tesla_fleet.const import DOMAIN
from homeassistant.components.tesla_fleet.services import (
    ATTR_DAYS_OF_WEEK,
    ATTR_ENABLE,
    ATTR_END_TIME,
    ATTR_ONE_TIME,
    ATTR_START_TIME,
    SERVICE_ADD_CHARGE_SCHEDULE,
    SERVICE_REMOVE_CHARGE_SCHEDULE,
)
from homeassistant.const import (
    ATTR_ID,
    ATTR_LOCATION,
    CONF_DEVICE_ID,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import setup_platform
from .const import COMMAND_ERROR, COMMAND_OK

from tests.common import MockConfigEntry

VEHICLE_VIN = "LRWXF7EK4KC700000"
ENERGY_SITE_ID = "123456"

LATITUDE = -27.9699373
LONGITUDE = 153.3726526

# A new schedule takes its ID from the current Unix time, which the tests freeze.
FROZEN_TIME = "2024-01-01 00:00:00+00:00"
GENERATED_ID = 1704067200

ADD_CHARGE_SCHEDULE = "tesla_fleet_api.tesla.VehicleFleet.add_charge_schedule"
REMOVE_CHARGE_SCHEDULE = "tesla_fleet_api.tesla.VehicleFleet.remove_charge_schedule"


async def _async_get_device_id(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    identifier: str,
) -> str:
    """Set up the integration and return the device ID for an identifier."""
    await setup_platform(hass, config_entry, [Platform.SENSOR])

    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, identifier), config_entry.entry_id
    )
    assert device is not None
    return device.id


@pytest.mark.parametrize(
    ("service_data", "expected_call"),
    [
        pytest.param(
            {
                ATTR_DAYS_OF_WEEK: ["monday", "tuesday"],
                ATTR_ENABLE: True,
                ATTR_LOCATION: {
                    CONF_LATITUDE: LATITUDE,
                    CONF_LONGITUDE: LONGITUDE,
                },
                ATTR_START_TIME: time(7, 0),
                ATTR_END_TIME: time(18, 30),
                ATTR_ONE_TIME: False,
                ATTR_ID: 3,
            },
            {
                "days_of_week": 6,
                "enabled": True,
                "lat": LATITUDE,
                "lon": LONGITUDE,
                "start_time": 420,
                "end_time": 1110,
                "one_time": False,
                "id": 3,
            },
            id="all_fields",
        ),
        pytest.param(
            {
                ATTR_DAYS_OF_WEEK: ["monday"],
                ATTR_ENABLE: True,
                ATTR_START_TIME: time(0, 30),
            },
            {
                "days_of_week": 2,
                "enabled": True,
                "lat": 32.87336,
                "lon": -117.22743,
                "start_time": 30,
                "end_time": None,
                "one_time": None,
                "id": GENERATED_ID,
            },
            id="minimal_fields_default_to_home_location",
        ),
        pytest.param(
            {
                ATTR_DAYS_OF_WEEK: [
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                ],
                ATTR_ENABLE: False,
                ATTR_END_TIME: time(23, 59),
            },
            {
                "days_of_week": 127,
                "enabled": False,
                "lat": 32.87336,
                "lon": -117.22743,
                "start_time": None,
                "end_time": 1439,
                "one_time": None,
                "id": GENERATED_ID,
            },
            id="every_day_is_full_bitmask",
        ),
        pytest.param(
            {
                ATTR_DAYS_OF_WEEK: ["sunday", "monday", "sunday"],
                ATTR_ENABLE: True,
                ATTR_START_TIME: time(6, 0),
            },
            {
                "days_of_week": 3,
                "enabled": True,
                "lat": 32.87336,
                "lon": -117.22743,
                "start_time": 360,
                "end_time": None,
                "one_time": None,
                "id": GENERATED_ID,
            },
            id="repeated_days_are_not_double_counted",
        ),
    ],
)
async def test_add_charge_schedule(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    service_data: dict[str, Any],
    expected_call: dict[str, Any],
) -> None:
    """Test add_charge_schedule sends the expected command."""
    freezer.move_to(FROZEN_TIME)
    device_id = await _async_get_device_id(hass, normal_config_entry, VEHICLE_VIN)

    with patch(ADD_CHARGE_SCHEDULE, return_value=COMMAND_OK) as call:
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CHARGE_SCHEDULE,
            {CONF_DEVICE_ID: device_id} | service_data,
            blocking=True,
            return_response=True,
        )

    call.assert_called_once_with(**expected_call)
    assert response == {"id": expected_call["id"]}


async def test_remove_charge_schedule(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Test remove_charge_schedule sends the expected command."""
    device_id = await _async_get_device_id(hass, normal_config_entry, VEHICLE_VIN)

    with patch(REMOVE_CHARGE_SCHEDULE, return_value=COMMAND_OK) as call:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_CHARGE_SCHEDULE,
            {CONF_DEVICE_ID: device_id, ATTR_ID: 3},
            blocking=True,
        )

    call.assert_called_once_with(id=3)


@pytest.mark.parametrize(
    "service_data",
    [
        pytest.param({}, id="no_times"),
        pytest.param({ATTR_START_TIME: time(0, 0)}, id="midnight_start_only"),
        pytest.param({ATTR_END_TIME: time(0, 0)}, id="midnight_end_only"),
        pytest.param(
            {ATTR_START_TIME: time(0, 0), ATTR_END_TIME: time(0, 0)},
            id="midnight_start_and_end",
        ),
    ],
)
async def test_add_charge_schedule_requires_a_time(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    service_data: dict[str, Any],
) -> None:
    """Test add_charge_schedule rejects a schedule without a usable time.

    The library treats a time of zero as absent, so midnight alone is rejected
    here rather than reaching the library and raising a bare ValueError.
    """
    device_id = await _async_get_device_id(hass, normal_config_entry, VEHICLE_VIN)

    with pytest.raises(ServiceValidationError, match="start time"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CHARGE_SCHEDULE,
            {
                CONF_DEVICE_ID: device_id,
                ATTR_DAYS_OF_WEEK: ["monday"],
                ATTR_ENABLE: True,
            }
            | service_data,
            blocking=True,
        )


async def test_add_charge_schedule_energy_site(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Test add_charge_schedule rejects a device that is not a vehicle."""
    device_id = await _async_get_device_id(hass, normal_config_entry, ENERGY_SITE_ID)

    with pytest.raises(ServiceValidationError, match="No vehicle data"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_CHARGE_SCHEDULE,
            {
                CONF_DEVICE_ID: device_id,
                ATTR_DAYS_OF_WEEK: ["monday"],
                ATTR_ENABLE: True,
                ATTR_START_TIME: time(7, 0),
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        pytest.param(
            SERVICE_ADD_CHARGE_SCHEDULE,
            {
                ATTR_DAYS_OF_WEEK: ["monday"],
                ATTR_ENABLE: True,
                ATTR_START_TIME: time(7, 0),
            },
            id="add",
        ),
        pytest.param(
            SERVICE_REMOVE_CHARGE_SCHEDULE,
            {ATTR_ID: 3},
            id="remove",
        ),
    ],
)
async def test_charge_schedule_without_scope(
    hass: HomeAssistant,
    readonly_config_entry: MockConfigEntry,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """Test the charge schedule services require the vehicle charging commands scope."""
    device_id = await _async_get_device_id(hass, readonly_config_entry, VEHICLE_VIN)

    with pytest.raises(ServiceValidationError, match="charging commands scope"):
        await hass.services.async_call(
            DOMAIN,
            service,
            {CONF_DEVICE_ID: device_id} | service_data,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "target", "service_data"),
    [
        pytest.param(
            SERVICE_ADD_CHARGE_SCHEDULE,
            ADD_CHARGE_SCHEDULE,
            {
                ATTR_DAYS_OF_WEEK: ["monday"],
                ATTR_ENABLE: True,
                ATTR_START_TIME: time(7, 0),
            },
            id="add",
        ),
        pytest.param(
            SERVICE_REMOVE_CHARGE_SCHEDULE,
            REMOVE_CHARGE_SCHEDULE,
            {ATTR_ID: 3},
            id="remove",
        ),
    ],
)
async def test_charge_schedule_command_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    service: str,
    target: str,
    service_data: dict[str, Any],
) -> None:
    """Test a failed command surfaces as an error to the caller."""
    device_id = await _async_get_device_id(hass, normal_config_entry, VEHICLE_VIN)

    with (
        patch(target, return_value=COMMAND_ERROR),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {CONF_DEVICE_ID: device_id} | service_data,
            blocking=True,
        )
