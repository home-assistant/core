"""Services for the Tesla Fleet integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tesla_fleet_api.const import Scope
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_LOCATION
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv

if TYPE_CHECKING:
    from . import TeslaFleetConfigEntry

from .const import DOMAIN
from .helpers import handle_vehicle_command, wake_up_vehicle
from .models import TeslaFleetVehicleData

_LOGGER = logging.getLogger(__name__)

ATTR_VALUE = "value"
ATTR_TYPE = "type"
ATTR_LOCALE = "locale"
ATTR_ORDER = "order"
ATTR_SUPERCHARGER_ID = "supercharger_id"

DEFAULT_NAVIGATION_TYPE = "share_ext_content_raw"

SERVICE_SEND_NAVIGATION_REQUEST = "send_navigation_request"
SERVICE_SEND_NAVIGATION_GPS_REQUEST = "send_navigation_gps_request"
SERVICE_SEND_NAVIGATION_SC_REQUEST = "send_navigation_supercharger_request"
SERVICE_SHARE_TO_VEHICLE = "share_to_vehicle"

SCHEMA_SEND_NAVIGATION_REQUEST = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_VALUE): cv.string,
        vol.Optional(ATTR_TYPE, default=DEFAULT_NAVIGATION_TYPE): cv.string,
        vol.Optional(ATTR_LOCALE): cv.string,
    }
)

SCHEMA_SEND_NAVIGATION_GPS_REQUEST = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_LOCATION): vol.Schema(
            {
                vol.Required(ATTR_LATITUDE): cv.latitude,
                vol.Required(ATTR_LONGITUDE): cv.longitude,
            }
        ),
        vol.Optional(ATTR_ORDER): vol.Coerce(int),
    }
)

SCHEMA_SEND_NAVIGATION_SC_REQUEST = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_SUPERCHARGER_ID): cv.string,
        vol.Optional(ATTR_ORDER): vol.Coerce(int),
    }
)


class TeslaFleetServiceHelper:
    """Helper class to encapsulate common logic for Tesla Fleet services."""

    def __init__(self, hass: HomeAssistant, entry: TeslaFleetConfigEntry) -> None:
        """Initialize the service helper."""
        self.hass = hass
        self.entry = entry
        self.runtime_data = getattr(entry, "runtime_data", None)
        if not self.runtime_data:
            _LOGGER.error(
                "TeslaFleetServiceHelper initialized without runtime_data on entry"
            )
            self.vehicle_id_to_data_map: dict[str, TeslaFleetVehicleData] = {}
        else:
            self.vehicle_id_to_data_map: dict[str, TeslaFleetVehicleData] = {
                vehicle.vin: vehicle for vehicle in self.runtime_data.vehicles
            }
        self.domain = DOMAIN

    async def get_vehicle_data_for_service(
        self, device_id: str
    ) -> TeslaFleetVehicleData:
        """Resolve device_id to TeslaFleetVehicleData and handle errors."""
        if not self.runtime_data:
            raise ServiceValidationError(
                "Integration runtime data not available for service."
            )

        device_reg = dr.async_get(self.hass)
        device_entry = device_reg.async_get(device_id)

        if not device_entry:
            raise ServiceValidationError(
                f"Device ID '{device_id}' not found in the device registry."
            )

        vehicle_identifier_from_registry: str | None = None
        for domain, identifier_value in device_entry.identifiers:
            if domain == self.domain:
                vehicle_identifier_from_registry = identifier_value
                break

        if not vehicle_identifier_from_registry:
            raise ServiceValidationError(
                f"Device (ID: {device_id}) does not have a {self.domain} specific identifier (VIN expected)."
            )

        vehicle = self.vehicle_id_to_data_map.get(vehicle_identifier_from_registry)
        if not vehicle:
            raise ServiceValidationError(
                f"Tesla vehicle with VIN '{vehicle_identifier_from_registry}' (associated with device "
                f"'{device_id}') is not currently available or loaded."
            )
        return vehicle


async def async_setup_services(
    hass: HomeAssistant, entry: TeslaFleetConfigEntry
) -> None:
    """Set up the Tesla Fleet services for the specified config entry."""

    if not hasattr(entry, "runtime_data") or not entry.runtime_data:
        _LOGGER.error(
            "Cannot set up Tesla Fleet services: runtime_data not found on config entry"
        )
        return

    if Scope.VEHICLE_CMDS not in entry.runtime_data.scopes:
        _LOGGER.debug(
            "Skipping Tesla Fleet vehicle command services for '%s': Missing scope %s",
            entry.title,
            Scope.VEHICLE_CMDS.value,
        )
        return

    service_helper = TeslaFleetServiceHelper(hass, entry)

    async def send_navigation_or_share_handler(call: ServiceCall) -> None:
        """Service handler for text/share navigation requests and general sharing."""
        vehicle = await service_helper.get_vehicle_data_for_service(
            call.data[ATTR_DEVICE_ID]
        )

        await wake_up_vehicle(vehicle)
        await handle_vehicle_command(
            vehicle.api.navigation_request(
                value=call.data[ATTR_VALUE],
                type=call.data[ATTR_TYPE],
                locale=call.data.get(ATTR_LOCALE),
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_NAVIGATION_REQUEST,
        send_navigation_or_share_handler,
        schema=SCHEMA_SEND_NAVIGATION_REQUEST,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SHARE_TO_VEHICLE, 
        send_navigation_or_share_handler, 
        schema=SCHEMA_SEND_NAVIGATION_REQUEST,
    )

    async def send_navigation_gps_request_handler(call: ServiceCall) -> None:
        """Service handler to send a GPS coordinate navigation request."""
        vehicle = await service_helper.get_vehicle_data_for_service(
            call.data[ATTR_DEVICE_ID]
        )
        loc = call.data[ATTR_LOCATION]
        latitude = loc[ATTR_LATITUDE]
        longitude = loc[ATTR_LONGITUDE]
        order = call.data.get(ATTR_ORDER)

        await wake_up_vehicle(vehicle)
        await handle_vehicle_command(
            vehicle.api.navigation_gps_request(
                lat=latitude,
                lon=longitude,
                order=order,
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_NAVIGATION_GPS_REQUEST,
        send_navigation_gps_request_handler,
        schema=SCHEMA_SEND_NAVIGATION_GPS_REQUEST,
    )

    async def send_navigation_sc_request_handler(call: ServiceCall) -> None:
        """Service handler to send a Supercharger navigation request."""
        vehicle = await service_helper.get_vehicle_data_for_service(
            call.data[ATTR_DEVICE_ID]
        )
        supercharger_id = call.data[ATTR_SUPERCHARGER_ID]
        # order = call.data.get(ATTR_ORDER)
        order = 0
        
        _LOGGER.error(
            "Super charger ID '%s': Order %s",
            supercharger_id,
            order
        )

        await wake_up_vehicle(vehicle)
        await handle_vehicle_command(
            vehicle.api.navigation_sc_request(
                id=supercharger_id,
                order=order,
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_NAVIGATION_SC_REQUEST,
        send_navigation_sc_request_handler,
        schema=SCHEMA_SEND_NAVIGATION_SC_REQUEST,
    )
