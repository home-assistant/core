"""Service calls for the Teslemetry integration."""

from enum import StrEnum
import logging

import probatio

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    service,
)

from .const import DOMAIN
from .helpers import handle_command, handle_energy_site_command, handle_vehicle_command
from .models import TeslemetryConfigEntry, TeslemetryEnergyData, TeslemetryVehicleData


class TeslemetryService(StrEnum):
    """Store keys for Teslemetry services."""

    NAVIGATION_GPS_REQUEST = "navigation_gps_request"
    TIME_OF_USE = "time_of_use"
    SET_SCHEDULED_CHARGING = "set_scheduled_charging"
    SET_SCHEDULED_DEPARTURE = "set_scheduled_departure"
    VALET_MODE = "valet_mode"
    SPEED_LIMIT = "speed_limit"
    ADD_CHARGE_SCHEDULE = "add_charge_schedule"
    REMOVE_CHARGE_SCHEDULE = "remove_charge_schedule"
    ADD_PRECONDITION_SCHEDULE = "add_precondition_schedule"
    REMOVE_PRECONDITION_SCHEDULE = "remove_precondition_schedule"
    DISPATCH_BATTERY_POWER = "dispatch_battery_power"
    RESUME_BATTERY_OPERATION = "resume_battery_operation"


class TeslemetryServiceArgument(StrEnum):
    """Store keys for Teslemetry service arguments."""

    GPS = "gps"
    ORDER = "order"
    TOU_SETTINGS = "tou_settings"
    ENABLE = "enable"
    TIME = "time"
    PRECONDITIONING_ENABLED = "preconditioning_enabled"
    PRECONDITIONING_WEEKDAYS_ONLY = "preconditioning_weekdays_only"
    DEPARTURE_TIME = "departure_time"
    OFF_PEAK_CHARGING_ENABLED = "off_peak_charging_enabled"
    OFF_PEAK_CHARGING_WEEKDAYS_ONLY = "off_peak_charging_weekdays_only"
    END_OFF_PEAK_TIME = "end_off_peak_time"
    PIN = "pin"
    DAYS_OF_WEEK = "days_of_week"
    LOCATION = "location"
    START_TIME = "start_time"
    END_TIME = "end_time"
    ONE_TIME = "one_time"
    ID = "id"
    NAME = "name"
    PRECONDITION_TIME = "precondition_time"
    POWER = "power"
    DURATION = "duration"


_LOGGER = logging.getLogger(__name__)

# Attributes

# Services

MAX_DISPATCH_POWER = 100000
MAX_DISPATCH_DURATION = 86400


def async_get_device_and_config_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> tuple[dr.DeviceEntry, TeslemetryConfigEntry]:
    """Get the device entry and config entry related to a service call."""
    config_entry: TeslemetryConfigEntry
    # Callers match the device's serial number, which only a main device has
    device_entry, config_entry = service.async_get_device_and_config_entry(
        hass,
        DOMAIN,
        call.data[CommonServiceArgument.DEVICE_ID],
        include_child_devices=False,
    )
    return device_entry, config_entry


def async_get_vehicle_for_entry(
    hass: HomeAssistant, device: dr.DeviceEntry, config: TeslemetryConfigEntry
) -> TeslemetryVehicleData:
    """Get the vehicle data for a config entry."""
    assert device.serial_number is not None
    for vehicle in config.runtime_data.vehicles:
        if vehicle.vin == device.serial_number:
            return vehicle
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="no_vehicle_data_for_device",
        translation_placeholders={"device_id": device.id},
    )


def async_get_energy_site_for_entry(
    hass: HomeAssistant, device: dr.DeviceEntry, config: TeslemetryConfigEntry
) -> TeslemetryEnergyData:
    """Get the energy site data for a config entry."""
    assert device.serial_number is not None
    for energysite in config.runtime_data.energysites:
        if str(energysite.id) == device.serial_number:
            return energysite
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="no_energy_site_data_for_device",
        translation_placeholders={"device_id": device.id},
    )


async def async_dispatch_battery_power(call: ServiceCall) -> None:
    """Charge or discharge the battery at a set power for a set time."""
    device, config = async_get_device_and_config_for_service_call(call.hass, call)
    site = async_get_energy_site_for_entry(call.hass, device, config)

    await handle_energy_site_command(
        site.api.dispatch_battery_power(
            call.data[TeslemetryServiceArgument.POWER],
            call.data[TeslemetryServiceArgument.DURATION],
        )
    )


async def async_resume_battery_operation(call: ServiceCall) -> None:
    """Return the battery to its configured operating mode."""
    device, config = async_get_device_and_config_for_service_call(call.hass, call)
    site = async_get_energy_site_for_entry(call.hass, device, config)

    await handle_energy_site_command(site.api.resume_battery_operation())


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Teslemetry services."""

    async def navigate_gps_request(call: ServiceCall) -> None:
        """Send lat,lon,order with a vehicle."""
        device, config = async_get_device_and_config_for_service_call(hass, call)
        vehicle = async_get_vehicle_for_entry(hass, device, config)

        await handle_vehicle_command(
            vehicle.api.navigation_gps_request(
                lat=call.data[TeslemetryServiceArgument.GPS][CONF_LATITUDE],
                lon=call.data[TeslemetryServiceArgument.GPS][CONF_LONGITUDE],
                order=call.data.get(TeslemetryServiceArgument.ORDER, 0),
            )
        )

    hass.services.async_register(
        DOMAIN,
        TeslemetryService.NAVIGATION_GPS_REQUEST,
        navigate_gps_request,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
                probatio.Required(TeslemetryServiceArgument.GPS): {
                    probatio.Required(CONF_LATITUDE): cv.latitude,
                    probatio.Required(CONF_LONGITUDE): cv.longitude,
                },
                probatio.Optional(TeslemetryServiceArgument.ORDER): cv.positive_int,
            }
        ),
    )

    async def set_scheduled_charging(call: ServiceCall) -> None:
        """Configure fleet telemetry."""
        device, config = async_get_device_and_config_for_service_call(hass, call)
        vehicle = async_get_vehicle_for_entry(hass, device, config)

        time: int
        # Convert time to minutes since minute
        if TeslemetryServiceArgument.TIME in call.data:
            (hours, minutes, *_seconds) = call.data[
                TeslemetryServiceArgument.TIME
            ].split(":")
            time = int(hours) * 60 + int(minutes)
        elif call.data[TeslemetryServiceArgument.ENABLE]:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="set_scheduled_charging_time"
            )
        else:
            time = 0

        await handle_vehicle_command(
            vehicle.api.set_scheduled_charging(
                enable=call.data[TeslemetryServiceArgument.ENABLE], time=time
            )
        )

    hass.services.async_register(
        DOMAIN,
        TeslemetryService.SET_SCHEDULED_CHARGING,
        set_scheduled_charging,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
                probatio.Required(TeslemetryServiceArgument.ENABLE): bool,
                probatio.Optional(TeslemetryServiceArgument.TIME): str,
            }
        ),
    )

    async def set_scheduled_departure(call: ServiceCall) -> None:
        """Configure fleet telemetry."""
        device, config = async_get_device_and_config_for_service_call(hass, call)
        vehicle = async_get_vehicle_for_entry(hass, device, config)

        enable = call.data.get(TeslemetryServiceArgument.ENABLE, True)

        # Preconditioning
        preconditioning_enabled = call.data.get(
            TeslemetryServiceArgument.PRECONDITIONING_ENABLED, False
        )
        preconditioning_weekdays_only = call.data.get(
            TeslemetryServiceArgument.PRECONDITIONING_WEEKDAYS_ONLY, False
        )
        departure_time: int | None = None
        if TeslemetryServiceArgument.DEPARTURE_TIME in call.data:
            (hours, minutes, *_seconds) = call.data[
                TeslemetryServiceArgument.DEPARTURE_TIME
            ].split(":")
            departure_time = int(hours) * 60 + int(minutes)
        elif preconditioning_enabled:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="set_scheduled_departure_preconditioning",
            )
        else:
            departure_time = 0

        # Off peak charging
        off_peak_charging_enabled = call.data.get(
            TeslemetryServiceArgument.OFF_PEAK_CHARGING_ENABLED, False
        )
        off_peak_charging_weekdays_only = call.data.get(
            TeslemetryServiceArgument.OFF_PEAK_CHARGING_WEEKDAYS_ONLY, False
        )
        end_off_peak_time: int | None = None

        if TeslemetryServiceArgument.END_OFF_PEAK_TIME in call.data:
            (hours, minutes, *_seconds) = call.data[
                TeslemetryServiceArgument.END_OFF_PEAK_TIME
            ].split(":")
            end_off_peak_time = int(hours) * 60 + int(minutes)
        elif off_peak_charging_enabled:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="set_scheduled_departure_off_peak",
            )
        else:
            end_off_peak_time = 0

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

    hass.services.async_register(
        DOMAIN,
        TeslemetryService.SET_SCHEDULED_DEPARTURE,
        set_scheduled_departure,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
                probatio.Optional(TeslemetryServiceArgument.ENABLE): bool,
                probatio.Optional(
                    TeslemetryServiceArgument.PRECONDITIONING_ENABLED
                ): bool,
                probatio.Optional(
                    TeslemetryServiceArgument.PRECONDITIONING_WEEKDAYS_ONLY
                ): bool,
                probatio.Optional(TeslemetryServiceArgument.DEPARTURE_TIME): str,
                probatio.Optional(
                    TeslemetryServiceArgument.OFF_PEAK_CHARGING_ENABLED
                ): bool,
                probatio.Optional(
                    TeslemetryServiceArgument.OFF_PEAK_CHARGING_WEEKDAYS_ONLY
                ): bool,
                probatio.Optional(TeslemetryServiceArgument.END_OFF_PEAK_TIME): str,
            }
        ),
    )

    async def valet_mode(call: ServiceCall) -> None:
        """Configure fleet telemetry."""
        device, config = async_get_device_and_config_for_service_call(hass, call)
        vehicle = async_get_vehicle_for_entry(hass, device, config)

        await handle_vehicle_command(
            vehicle.api.set_valet_mode(
                call.data[TeslemetryServiceArgument.ENABLE],
                call.data[TeslemetryServiceArgument.PIN],
            )
        )

    hass.services.async_register(
        DOMAIN,
        TeslemetryService.VALET_MODE,
        valet_mode,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
                probatio.Required(TeslemetryServiceArgument.ENABLE): cv.boolean,
                probatio.Required(TeslemetryServiceArgument.PIN): probatio.All(
                    cv.positive_int, probatio.Range(min=1000, max=9999)
                ),
            }
        ),
    )

    async def speed_limit(call: ServiceCall) -> None:
        """Configure fleet telemetry."""
        device, config = async_get_device_and_config_for_service_call(hass, call)
        vehicle = async_get_vehicle_for_entry(hass, device, config)

        enable = call.data[TeslemetryServiceArgument.ENABLE]
        if enable is True:
            await handle_vehicle_command(
                vehicle.api.speed_limit_activate(
                    call.data[TeslemetryServiceArgument.PIN]
                )
            )
        elif enable is False:
            await handle_vehicle_command(
                vehicle.api.speed_limit_deactivate(
                    call.data[TeslemetryServiceArgument.PIN]
                )
            )

    hass.services.async_register(
        DOMAIN,
        TeslemetryService.SPEED_LIMIT,
        speed_limit,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
                probatio.Required(TeslemetryServiceArgument.ENABLE): cv.boolean,
                probatio.Required(TeslemetryServiceArgument.PIN): probatio.All(
                    cv.positive_int, probatio.Range(min=1000, max=9999)
                ),
            }
        ),
    )

    async def time_of_use(call: ServiceCall) -> None:
        """Configure time of use settings."""
        device, config = async_get_device_and_config_for_service_call(hass, call)
        site = async_get_energy_site_for_entry(hass, device, config)

        tou_settings = call.data[TeslemetryServiceArgument.TOU_SETTINGS]
        # Unwrap tariff_content_v2 if user included it, since the SDK adds this wrapper
        if "tariff_content_v2" in tou_settings:
            tou_settings = tou_settings["tariff_content_v2"]

        resp = await handle_command(site.api.time_of_use_settings(tou_settings))
        if "error" in resp:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_error",
                translation_placeholders={"error": resp["error"]},
            )

    hass.services.async_register(
        DOMAIN,
        TeslemetryService.TIME_OF_USE,
        time_of_use,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
                probatio.Required(TeslemetryServiceArgument.TOU_SETTINGS): dict,
            }
        ),
        description_placeholders={
            "time_of_use_url": "https://developer.tesla.com/docs/fleet-api#time_of_use_settings"
        },
    )

    async def add_charge_schedule(call: ServiceCall) -> None:
        """Configure charging schedule for a vehicle."""
        device, config = async_get_device_and_config_for_service_call(hass, call)
        vehicle = async_get_vehicle_for_entry(hass, device, config)

        # Extract parameters from the service call
        days_of_week = call.data[TeslemetryServiceArgument.DAYS_OF_WEEK]
        # If days_of_week is a list (from select with
        # multiple), convert to comma-separated string
        if isinstance(days_of_week, list):
            days_of_week = ",".join(days_of_week)
        enabled = call.data[TeslemetryServiceArgument.ENABLE]

        # Optional parameters
        location = call.data.get(
            TeslemetryServiceArgument.LOCATION,
            {
                CONF_LATITUDE: hass.config.latitude,
                CONF_LONGITUDE: hass.config.longitude,
            },
        )

        # Handle time inputs
        start_time = None
        if start_time_obj := call.data.get(TeslemetryServiceArgument.START_TIME):
            # Convert time object to minutes since midnight
            start_time = start_time_obj.hour * 60 + start_time_obj.minute

        end_time = None
        if end_time_obj := call.data.get(TeslemetryServiceArgument.END_TIME):
            # Convert time object to minutes since midnight
            end_time = end_time_obj.hour * 60 + end_time_obj.minute

        one_time = call.data.get(TeslemetryServiceArgument.ONE_TIME)
        schedule_id = call.data.get(TeslemetryServiceArgument.ID)
        name = call.data.get(TeslemetryServiceArgument.NAME)

        await handle_vehicle_command(
            vehicle.api.add_charge_schedule(
                days_of_week=days_of_week,
                enabled=enabled,
                lat=location[CONF_LATITUDE],
                lon=location[CONF_LONGITUDE],
                start_time=start_time,
                end_time=end_time,
                one_time=one_time,
                id=schedule_id,
                name=name,
            )
        )

    hass.services.async_register(
        DOMAIN,
        TeslemetryService.ADD_CHARGE_SCHEDULE,
        add_charge_schedule,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
                probatio.Required(
                    TeslemetryServiceArgument.DAYS_OF_WEEK
                ): probatio.EnsureList(),
                probatio.Required(TeslemetryServiceArgument.ENABLE): cv.boolean,
                probatio.Optional(TeslemetryServiceArgument.LOCATION): {
                    probatio.Required(CONF_LATITUDE): cv.latitude,
                    probatio.Required(CONF_LONGITUDE): cv.longitude,
                },
                probatio.Optional(TeslemetryServiceArgument.START_TIME): cv.time,
                probatio.Optional(TeslemetryServiceArgument.END_TIME): cv.time,
                probatio.Optional(TeslemetryServiceArgument.ONE_TIME): cv.boolean,
                probatio.Optional(TeslemetryServiceArgument.ID): cv.positive_int,
                probatio.Optional(TeslemetryServiceArgument.NAME): cv.string,
            }
        ),
    )

    async def remove_charge_schedule(call: ServiceCall) -> None:
        """Remove a charging schedule for a vehicle."""
        device, config = async_get_device_and_config_for_service_call(hass, call)
        vehicle = async_get_vehicle_for_entry(hass, device, config)

        # Extract parameters from the service call
        schedule_id = call.data[TeslemetryServiceArgument.ID]

        await handle_vehicle_command(
            vehicle.api.remove_charge_schedule(
                id=schedule_id,
            )
        )

    hass.services.async_register(
        DOMAIN,
        TeslemetryService.REMOVE_CHARGE_SCHEDULE,
        remove_charge_schedule,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
                probatio.Required(TeslemetryServiceArgument.ID): cv.positive_int,
            }
        ),
    )

    async def add_precondition_schedule(call: ServiceCall) -> None:
        """Add or modify a precondition schedule for a vehicle."""
        device, config = async_get_device_and_config_for_service_call(hass, call)
        vehicle = async_get_vehicle_for_entry(hass, device, config)

        # Extract parameters from the service call
        days_of_week = call.data[TeslemetryServiceArgument.DAYS_OF_WEEK]
        # If days_of_week is a list (from select with
        # multiple), convert to comma-separated string
        if isinstance(days_of_week, list):
            days_of_week = ",".join(days_of_week)
        enabled = call.data[TeslemetryServiceArgument.ENABLE]
        location = call.data.get(
            TeslemetryServiceArgument.LOCATION,
            {
                CONF_LATITUDE: hass.config.latitude,
                CONF_LONGITUDE: hass.config.longitude,
            },
        )

        # Convert time object to minutes since midnight
        precondition_time = (
            call.data[TeslemetryServiceArgument.PRECONDITION_TIME].hour * 60
            + call.data[TeslemetryServiceArgument.PRECONDITION_TIME].minute
        )

        # Optional parameters
        schedule_id = call.data.get(TeslemetryServiceArgument.ID)
        one_time = call.data.get(TeslemetryServiceArgument.ONE_TIME)
        name = call.data.get(TeslemetryServiceArgument.NAME)

        await handle_vehicle_command(
            vehicle.api.add_precondition_schedule(
                days_of_week=days_of_week,
                enabled=enabled,
                lat=location[CONF_LATITUDE],
                lon=location[CONF_LONGITUDE],
                precondition_time=precondition_time,
                id=schedule_id,
                one_time=one_time,
                name=name,
            )
        )

    hass.services.async_register(
        DOMAIN,
        TeslemetryService.ADD_PRECONDITION_SCHEDULE,
        add_precondition_schedule,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
                probatio.Required(
                    TeslemetryServiceArgument.DAYS_OF_WEEK
                ): probatio.EnsureList(),
                probatio.Required(TeslemetryServiceArgument.ENABLE): cv.boolean,
                probatio.Optional(TeslemetryServiceArgument.LOCATION): {
                    probatio.Required(CONF_LATITUDE): cv.latitude,
                    probatio.Required(CONF_LONGITUDE): cv.longitude,
                },
                probatio.Required(TeslemetryServiceArgument.PRECONDITION_TIME): cv.time,
                probatio.Optional(TeslemetryServiceArgument.ID): cv.positive_int,
                probatio.Optional(TeslemetryServiceArgument.ONE_TIME): cv.boolean,
                probatio.Optional(TeslemetryServiceArgument.NAME): cv.string,
            }
        ),
    )

    async def remove_precondition_schedule(call: ServiceCall) -> None:
        """Remove a preconditioning schedule for a vehicle."""
        device, config = async_get_device_and_config_for_service_call(hass, call)
        vehicle = async_get_vehicle_for_entry(hass, device, config)

        # Extract parameters from the service call
        schedule_id = call.data[TeslemetryServiceArgument.ID]

        await handle_vehicle_command(
            vehicle.api.remove_precondition_schedule(
                id=schedule_id,
            )
        )

    hass.services.async_register(
        DOMAIN,
        TeslemetryService.REMOVE_PRECONDITION_SCHEDULE,
        remove_precondition_schedule,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
                probatio.Required(TeslemetryServiceArgument.ID): cv.positive_int,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        TeslemetryService.DISPATCH_BATTERY_POWER,
        async_dispatch_battery_power,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
                probatio.Required(TeslemetryServiceArgument.POWER): probatio.All(
                    probatio.Coerce(int),
                    probatio.Range(min=-MAX_DISPATCH_POWER, max=MAX_DISPATCH_POWER),
                ),
                probatio.Required(TeslemetryServiceArgument.DURATION): probatio.All(
                    cv.positive_int, probatio.Range(min=1, max=MAX_DISPATCH_DURATION)
                ),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        TeslemetryService.RESUME_BATTERY_OPERATION,
        async_resume_battery_operation,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
            }
        ),
    )
