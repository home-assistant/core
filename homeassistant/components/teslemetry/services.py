"""Service calls for the Teslemetry integration."""

import logging

from tesla_fleet_api.exceptions import TeslaFleetError
import voluptuous as vol
from voluptuous import All, Range

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .helpers import handle_vehicle_command, wake_up_vehicle
from .models import TeslemetryEnergyData, TeslemetryVehicleData

_LOGGER = logging.getLogger(__name__)

# Attributes
ATTR_ID = "id"
ATTR_GPS = "gps"
ATTR_TYPE = "type"
ATTR_VALUE = "value"
ATTR_LOCALE = "locale"
ATTR_ORDER = "order"
ATTR_TIMESTAMP = "timestamp"
ATTR_FIELDS = "fields"
ATTR_ENABLE = "enable"
ATTR_TIME = "time"
ATTR_PIN = "pin"
ATTR_TOU_SETTINGS = "tou_settings"
ATTR_PRECODITIONING_ENABLED = "preconditioning_enabled"
ATTR_PRECODITIONING_WEEKDAYS = "preconditioning_weekdays_only"
ATTR_DEPARTURE_TIME = "departure_time"
ATTR_OFF_PEAK_CHARGING_ENABLED = "off_peak_charging_enabled"
ATTR_OFF_PEAK_CHARGING_WEEKDAYS = "off_peak_charging_weekdays_only"
ATTR_END_OFF_PEAK_TIME = "end_off_peak_time"

# Services
SERVICE_NAVIGATE_ATTR_GPS_REQUEST = "navigation_gps_request"
SERVICE_SET_SCHEDULED_CHARGING = "set_scheduled_charging"
SERVICE_SET_SCHEDULED_DEPARTURE = "set_scheduled_departure"
SERVICE_VALET_MODE = "valet_mode"
SERVICE_SPEED_LIMIT = "speed_limit"
SERVICE_TIME_OF_USE = "time_of_use"


def async_get_device_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> dr.DeviceEntry:
    """Get the device entry related to a service call."""
    device_id = call.data[CONF_DEVICE_ID]
    device_registry = dr.async_get(hass)
    if (device_entry := device_registry.async_get(device_id)) is None:
        raise ServiceValidationError(f"Invalid device ATTR_ID: {device_id}")
    return device_entry


def async_get_config_for_device(
    hass: HomeAssistant, device_entry: dr.DeviceEntry
) -> ConfigEntry:
    """Get the config entry related to a device entry."""
    for entry_id in device_entry.config_entries:
        if (entry := hass.config_entries.async_get_entry(entry_id)) is None:
            continue
        if entry.domain == DOMAIN:
            return entry
    raise ServiceValidationError(
        f"No config entry for device ATTR_ID: {device_entry.id}"
    )


def async_get_vehicle_for_entry(
    hass: HomeAssistant, device: dr.DeviceEntry, config: ConfigEntry
) -> TeslemetryVehicleData:
    """Get the vehicle data for a config entry."""
    assert device.serial_number is not None
    for vehicle in config.runtime_data.vehicles:
        if vehicle.vin == device.serial_number:
            return vehicle
    raise ServiceValidationError(f"No vehicle data for device ATTR_ID: {device.id}")


def async_get_energy_site_for_entry(
    hass: HomeAssistant, device: dr.DeviceEntry, config: ConfigEntry
) -> TeslemetryEnergyData:
    """Get the energy site data for a config entry."""
    assert device.serial_number is not None
    for site in config.runtime_data.energy_sites:
        if site.id == device.serial_number:
            return site
    raise ServiceValidationError(f"No energy site for device ATTR_ID: {device.id}")


def async_register_services(hass: HomeAssistant) -> None:  # noqa: C901
    """Set up the Teslemetry services."""

    _LOGGER.info("Registering services")

    async def navigate_gps_request(call: ServiceCall) -> None:
        """Send lat,lon,order with a vehicle."""
        device = async_get_device_for_service_call(hass, call)
        config = async_get_config_for_device(hass, device)
        vehicle = async_get_vehicle_for_entry(hass, device, config)

        try:
            await wake_up_vehicle(vehicle)
            await handle_vehicle_command(
                vehicle.api.navigation_gps_request(
                    lat=call.data[ATTR_GPS][CONF_LATITUDE],
                    lon=call.data[ATTR_GPS][CONF_LONGITUDE],
                    order=call.data.get(ATTR_ORDER),
                )
            )
        except TeslaFleetError as e:
            raise HomeAssistantError from e

    hass.services.async_register(
        DOMAIN,
        SERVICE_NAVIGATE_ATTR_GPS_REQUEST,
        navigate_gps_request,
        schema=vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): cv.string,
                vol.Required(ATTR_GPS): {
                    vol.Required(CONF_LATITUDE): cv.latitude,
                    vol.Required(CONF_LONGITUDE): cv.longitude,
                },
                vol.Optional(ATTR_ORDER): cv.positive_int,
            }
        ),
    )

    async def set_scheduled_charging(call: ServiceCall) -> None:
        """Configure fleet telemetry."""
        device = async_get_device_for_service_call(hass, call)
        config = async_get_config_for_device(hass, device)
        vehicle = async_get_vehicle_for_entry(hass, device, config)

        # Convert time to minutes since minute
        if "time" in call.data:
            (hours, minutes, *seconds) = call.data["time"].split(":")
            time = int(hours) * 60 + int(minutes)
        elif call.data["enable"]:
            raise ServiceValidationError("Time required to enable scheduled charging")
        else:
            time = None

        try:
            await wake_up_vehicle(vehicle)
            await handle_vehicle_command(
                vehicle.api.set_scheduled_charging(
                    enable=call.data["enable"], time=time
                )
            )
        except TeslaFleetError as e:
            raise HomeAssistantError from e

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCHEDULED_CHARGING,
        set_scheduled_charging,
        schema=vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): cv.string,
                vol.Required(ATTR_ENABLE): bool,
                vol.Optional(ATTR_TIME): str,
            }
        ),
    )

    async def set_scheduled_departure(call: ServiceCall) -> None:
        """Configure fleet telemetry."""
        device = async_get_device_for_service_call(hass, call)
        config = async_get_config_for_device(hass, device)
        vehicle = async_get_vehicle_for_entry(hass, device, config)

        enable = call.data.get("enable", True)

        # Preconditioning
        preconditioning_enabled = call.data.get("preconditioning_enabled", False)
        preconditioning_weekdays_only = call.data.get(
            "preconditioning_weekdays_only", False
        )
        if "departure_time" in call.data:
            (hours, minutes, *seconds) = call.data["departure_time"].split(":")
            departure_time = int(hours) * 60 + int(minutes)
        elif preconditioning_enabled:
            raise ServiceValidationError(
                "Departure time required to enable preconditioning"
            )
        else:
            departure_time = 0

        # Off peak charging
        off_peak_charging_enabled = call.data.get("off_peak_charging_enabled", False)
        off_peak_charging_weekdays_only = call.data.get(
            "off_peak_charging_weekdays_only", False
        )
        if "end_off_peak_time" in call.data:
            (hours, minutes, *seconds) = call.data["end_off_peak_time"].split(":")
            end_off_peak_time = int(hours) * 60 + int(minutes)
        elif off_peak_charging_enabled:
            raise ServiceValidationError(
                "End off peak time required to enable off peak charging"
            )
        else:
            end_off_peak_time = 0

        try:
            await wake_up_vehicle(vehicle)
            await handle_vehicle_command(
                vehicle.api.set_scheduled_departure(
                    enable,
                    preconditioning_enabled,
                    preconditioning_weekdays_only,
                    departure_time,
                    off_peak_charging_enabled,
                    off_peak_charging_weekdays_only,
                    end_off_peak_time,
                )
            )

        except TeslaFleetError as e:
            raise HomeAssistantError from e

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCHEDULED_DEPARTURE,
        set_scheduled_departure,
        schema=vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): cv.string,
                vol.Optional(ATTR_ENABLE): bool,
                vol.Optional(ATTR_PRECODITIONING_ENABLED): bool,
                vol.Optional(ATTR_PRECODITIONING_WEEKDAYS): bool,
                vol.Optional(ATTR_DEPARTURE_TIME): str,
                vol.Optional(ATTR_OFF_PEAK_CHARGING_ENABLED): bool,
                vol.Optional(ATTR_OFF_PEAK_CHARGING_WEEKDAYS): bool,
                vol.Optional(ATTR_END_OFF_PEAK_TIME): str,
            }
        ),
    )

    async def valet_mode(call: ServiceCall) -> None:
        """Configure fleet telemetry."""
        device = async_get_device_for_service_call(hass, call)
        config = async_get_config_for_device(hass, device)
        vehicle = async_get_vehicle_for_entry(hass, device, config)

        try:
            await wake_up_vehicle(vehicle)
            await handle_vehicle_command(
                vehicle.api.set_valet_mode(
                    call.data.get("enable"), call.data.get("pin", "")
                )
            )

        except TeslaFleetError as e:
            raise HomeAssistantError from e

    hass.services.async_register(
        DOMAIN,
        SERVICE_VALET_MODE,
        valet_mode,
        schema=vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): cv.string,
                vol.Required(ATTR_ENABLE): cv.boolean,
                vol.Required(ATTR_PIN): All(cv.positive_int, Range(min=1000, max=9999)),
            }
        ),
    )

    async def speed_limit(call: ServiceCall) -> None:
        """Configure fleet telemetry."""
        device = async_get_device_for_service_call(hass, call)
        config = async_get_config_for_device(hass, device)
        vehicle = async_get_vehicle_for_entry(hass, device, config)

        try:
            await wake_up_vehicle(vehicle)
            enable = call.data.get("enable")
            if enable is True:
                await handle_vehicle_command(
                    vehicle.api.speed_limit_activate(call.data.get("pin"))
                )
            elif enable is False:
                await handle_vehicle_command(
                    vehicle.api.speed_limit_deactivate(call.data.get("pin"))
                )

        except TeslaFleetError as e:
            raise HomeAssistantError from e

    hass.services.async_register(
        DOMAIN,
        SERVICE_SPEED_LIMIT,
        speed_limit,
        schema=vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): cv.string,
                vol.Required(ATTR_ENABLE): cv.boolean,
                vol.Required(ATTR_PIN): All(cv.positive_int, Range(min=1000, max=9999)),
            }
        ),
    )

    async def time_of_use(call: ServiceCall) -> None:
        """Configure time of use settings."""
        device = async_get_device_for_service_call(hass, call)
        config = async_get_config_for_device(hass, device)
        site = async_get_energy_site_for_entry(hass, device, config)

        try:
            resp = await site.api.time_of_use_settings(call.data.get(ATTR_TOU_SETTINGS))
        except Exception as e:
            raise HomeAssistantError from e
        if "error" in resp:
            raise ServiceValidationError(resp["error"])

    hass.services.async_register(
        DOMAIN,
        SERVICE_TIME_OF_USE,
        time_of_use,
        schema=vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): cv.string,
                vol.Required(ATTR_TOU_SETTINGS): dict,
            }
        ),
    )
