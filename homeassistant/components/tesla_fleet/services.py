"""Service calls for the Tesla Fleet integration."""

from typing import TYPE_CHECKING

import probatio
from tesla_fleet_api.const import Scope

from homeassistant.const import CONF_DEVICE_ID, CONF_LATITUDE, CONF_LONGITUDE
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

# Attributes
ATTR_DESTINATION = "destination"
ATTR_GPS = "gps"
ATTR_ORDER = "order"

# Services
SERVICE_NAVIGATION_REQUEST = "navigation_request"
SERVICE_NAVIGATION_GPS_REQUEST = "navigation_gps_request"


def async_get_vehicle_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> TeslaFleetVehicleData:
    """Get the vehicle targeted by a service call and ensure it accepts commands."""
    device: dr.DeviceEntry
    config: TeslaFleetConfigEntry
    # Vehicles are matched by serial number, which only a main device has
    device, config = service.async_get_device_and_config_entry(
        hass, DOMAIN, call.data[CONF_DEVICE_ID], include_child_devices=False
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

    async def navigation_request(call: ServiceCall) -> None:
        """Send an address, place name or map link to a vehicle."""
        vehicle = async_get_vehicle_for_service_call(hass, call)
        await wake_up_vehicle(vehicle)
        await handle_vehicle_command(
            vehicle.api.navigation_request(call.data[ATTR_DESTINATION])
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_NAVIGATION_REQUEST,
        navigation_request,
        schema=probatio.Schema(
            {
                probatio.Required(CONF_DEVICE_ID): cv.string,
                probatio.Required(ATTR_DESTINATION): cv.string,
            }
        ),
    )

    async def navigation_gps_request(call: ServiceCall) -> None:
        """Send coordinates to a vehicle."""
        vehicle = async_get_vehicle_for_service_call(hass, call)
        await wake_up_vehicle(vehicle)
        await handle_vehicle_command(
            vehicle.api.navigation_gps_request(
                lat=call.data[ATTR_GPS][CONF_LATITUDE],
                lon=call.data[ATTR_GPS][CONF_LONGITUDE],
                order=call.data[ATTR_ORDER],
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_NAVIGATION_GPS_REQUEST,
        navigation_gps_request,
        schema=probatio.Schema(
            {
                probatio.Required(CONF_DEVICE_ID): cv.string,
                probatio.Required(ATTR_GPS): {
                    probatio.Required(CONF_LATITUDE): cv.latitude,
                    probatio.Required(CONF_LONGITUDE): cv.longitude,
                },
                probatio.Optional(ATTR_ORDER, default=1): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=1, max=3)
                ),
            }
        ),
    )
