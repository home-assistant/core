"""Service calls for the Tesla Fleet integration."""

from enum import StrEnum
from typing import TYPE_CHECKING

import probatio
from tesla_fleet_api.const import Scope

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    service,
)

from .const import DOMAIN
from .helpers import handle_vehicle_command, wake_up_vehicle
from .models import TeslaFleetVehicleData

if TYPE_CHECKING:
    from . import TeslaFleetConfigEntry


class TeslaFleetService(StrEnum):
    """Store keys for Tesla Fleet services."""

    NAVIGATE_TO_DESTINATION = "navigate_to_destination"
    NAVIGATE_TO_COORDINATES = "navigate_to_coordinates"
    NAVIGATE_TO_WAYPOINTS = "navigate_to_waypoints"


class TeslaFleetServiceArgument(StrEnum):
    """Store keys for Tesla Fleet service arguments."""

    DESTINATION = "destination"
    GPS = "gps"
    PLACE_IDS = "place_ids"


def async_get_vehicle_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> TeslaFleetVehicleData:
    """Get the vehicle targeted by a service call and ensure it accepts commands."""
    device: dr.DeviceEntry
    config: TeslaFleetConfigEntry
    # Vehicles are matched by serial number, which only a main device has
    device, config = service.async_get_device_and_config_entry(
        hass,
        DOMAIN,
        call.data[CommonServiceArgument.DEVICE_ID],
        include_child_devices=False,
    )
    if Scope.VEHICLE_CMDS not in config.runtime_data.scopes:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_scope_vehicle_cmds",
        )
    for vehicle in config.runtime_data.vehicles:
        if vehicle.vin == device.serial_number:
            return vehicle
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="no_vehicle_data_for_device",
        translation_placeholders={"device_id": device.id},
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Tesla Fleet services."""

    async def navigate_to_destination(call: ServiceCall) -> None:
        """Send an address, place name or map link to a vehicle."""
        vehicle = async_get_vehicle_for_service_call(hass, call)
        await wake_up_vehicle(vehicle)
        await handle_vehicle_command(
            vehicle.api.navigation_request(
                call.data[TeslaFleetServiceArgument.DESTINATION]
            )
        )

    hass.services.async_register(
        DOMAIN,
        TeslaFleetService.NAVIGATE_TO_DESTINATION,
        navigate_to_destination,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
                probatio.Required(TeslaFleetServiceArgument.DESTINATION): cv.string,
            }
        ),
    )

    async def navigate_to_coordinates(call: ServiceCall) -> None:
        """Send coordinates to a vehicle."""
        vehicle = async_get_vehicle_for_service_call(hass, call)
        await wake_up_vehicle(vehicle)
        await handle_vehicle_command(
            vehicle.api.navigation_gps_request(
                lat=call.data[TeslaFleetServiceArgument.GPS][CONF_LATITUDE],
                lon=call.data[TeslaFleetServiceArgument.GPS][CONF_LONGITUDE],
            )
        )

    hass.services.async_register(
        DOMAIN,
        TeslaFleetService.NAVIGATE_TO_COORDINATES,
        navigate_to_coordinates,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
                probatio.Required(TeslaFleetServiceArgument.GPS): {
                    probatio.Required(CONF_LATITUDE): cv.latitude,
                    probatio.Required(CONF_LONGITUDE): cv.longitude,
                },
            }
        ),
    )

    async def navigate_to_waypoints(call: ServiceCall) -> None:
        """Send an ordered trip using caller-supplied Google Place IDs."""
        vehicle = async_get_vehicle_for_service_call(hass, call)
        await wake_up_vehicle(vehicle)
        await handle_vehicle_command(
            vehicle.api.navigation_waypoints_request(
                ",".join(
                    f"refId:{place_id}"
                    for place_id in call.data[TeslaFleetServiceArgument.PLACE_IDS]
                )
            )
        )

    hass.services.async_register(
        DOMAIN,
        TeslaFleetService.NAVIGATE_TO_WAYPOINTS,
        navigate_to_waypoints,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
                probatio.Required(TeslaFleetServiceArgument.PLACE_IDS): probatio.All(
                    [probatio.All(str, probatio.Match(r"^[^\s,:]+\Z"))],
                    probatio.Length(min=1),
                ),
            }
        ),
    )
