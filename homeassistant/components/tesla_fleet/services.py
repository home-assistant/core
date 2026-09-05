"""Service calls for the Tesla Fleet integration."""

from datetime import time
from typing import TYPE_CHECKING

from tesla_fleet_api.const import Scope
import voluptuous as vol

from homeassistant.const import (
    ATTR_ID,
    ATTR_LOCATION,
    CONF_DEVICE_ID,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.util import dt as dt_util

from .const import DAYS_OF_WEEK_BITS, DOMAIN
from .helpers import handle_vehicle_command, wake_up_vehicle
from .models import TeslaFleetVehicleData

if TYPE_CHECKING:
    from . import TeslaFleetConfigEntry

ATTR_DAYS_OF_WEEK = "days_of_week"
ATTR_ENABLE = "enable"
ATTR_END_TIME = "end_time"
ATTR_ONE_TIME = "one_time"
ATTR_START_TIME = "start_time"

# The vehicle rejects an ID of zero, which the selector also disallows.
SCHEDULE_ID = vol.All(cv.positive_int, vol.Range(min=1))

SERVICE_ADD_CHARGE_SCHEDULE = "add_charge_schedule"
SERVICE_REMOVE_CHARGE_SCHEDULE = "remove_charge_schedule"


def _days_of_week_bitmask(days: list[str]) -> int:
    """Convert selected day names into Tesla's day bitmask."""
    bitmask = 0
    for day in days:
        bitmask |= DAYS_OF_WEEK_BITS[day]
    return bitmask


def _minutes_after_midnight(value: time | None) -> int | None:
    """Convert a time into minutes after midnight."""
    if value is None:
        return None
    return value.hour * 60 + value.minute


def _get_vehicle_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> TeslaFleetVehicleData:
    """Get the vehicle a charging service call targets."""
    config_entry: TeslaFleetConfigEntry
    device, config_entry = service.async_get_device_and_config_entry(
        hass, DOMAIN, call.data[CONF_DEVICE_ID]
    )

    vehicle = next(
        (
            vehicle
            for vehicle in config_entry.runtime_data.vehicles
            if vehicle.vin == device.serial_number
        ),
        None,
    )
    if vehicle is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_vehicle_data_for_device",
            translation_placeholders={
                "device": device.name_by_user or device.name or device.id
            },
        )

    if Scope.VEHICLE_CHARGING_CMDS not in config_entry.runtime_data.scopes:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_scope_vehicle_charging_cmds",
        )

    return vehicle


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Tesla Fleet services."""

    async def add_charge_schedule(call: ServiceCall) -> ServiceResponse:
        """Add or modify a charge schedule for a vehicle."""
        vehicle = _get_vehicle_for_service_call(hass, call)

        start_time = _minutes_after_midnight(call.data.get(ATTR_START_TIME))
        end_time = _minutes_after_midnight(call.data.get(ATTR_END_TIME))
        if start_time is None and end_time is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="charge_schedule_requires_time",
            )

        location = call.data.get(
            ATTR_LOCATION,
            {
                CONF_LATITUDE: hass.config.latitude,
                CONF_LONGITUDE: hass.config.longitude,
            },
        )

        # The vehicle does not allocate an ID for a new schedule, so follow
        # Tesla's own client and derive one from the current Unix time. Two
        # calls would only collide by landing in the same second, which the
        # round trip to Tesla's API makes practically impossible.
        schedule_id = call.data.get(ATTR_ID, int(dt_util.utcnow().timestamp()))

        await wake_up_vehicle(vehicle)
        await handle_vehicle_command(
            vehicle.api.add_charge_schedule(
                days_of_week=_days_of_week_bitmask(call.data[ATTR_DAYS_OF_WEEK]),
                enabled=call.data[ATTR_ENABLE],
                lat=location[CONF_LATITUDE],
                lon=location[CONF_LONGITUDE],
                start_time=start_time,
                end_time=end_time,
                one_time=call.data.get(ATTR_ONE_TIME),
                id=schedule_id,
            )
        )
        return {"id": schedule_id}

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_CHARGE_SCHEDULE,
        add_charge_schedule,
        schema=vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): cv.string,
                vol.Required(ATTR_DAYS_OF_WEEK): vol.All(
                    cv.ensure_list, vol.Length(min=1), [vol.In(DAYS_OF_WEEK_BITS)]
                ),
                vol.Required(ATTR_ENABLE): cv.boolean,
                vol.Optional(ATTR_LOCATION): {
                    vol.Required(CONF_LATITUDE): cv.latitude,
                    vol.Required(CONF_LONGITUDE): cv.longitude,
                },
                vol.Optional(ATTR_START_TIME): cv.time,
                vol.Optional(ATTR_END_TIME): cv.time,
                vol.Optional(ATTR_ONE_TIME): cv.boolean,
                vol.Optional(ATTR_ID): SCHEDULE_ID,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def remove_charge_schedule(call: ServiceCall) -> None:
        """Remove a charge schedule from a vehicle."""
        vehicle = _get_vehicle_for_service_call(hass, call)

        await wake_up_vehicle(vehicle)
        await handle_vehicle_command(
            vehicle.api.remove_charge_schedule(id=call.data[ATTR_ID])
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_CHARGE_SCHEDULE,
        remove_charge_schedule,
        schema=vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): cv.string,
                vol.Required(ATTR_ID): SCHEDULE_ID,
            }
        ),
    )
