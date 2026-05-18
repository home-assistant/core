"""Service calls for the Tessie integration."""

from __future__ import annotations

import logging

from tesla_fleet_api.exceptions import TeslaFleetError
from tessie_api import set_scheduled_charging, set_scheduled_departure
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .models import TessieVehicleData

_LOGGER = logging.getLogger(__name__)

ATTR_ENABLE = "enable"
ATTR_TIME = "time"
ATTR_PRECONDITIONING_ENABLED = "preconditioning_enabled"
ATTR_PRECONDITIONING_WEEKDAYS = "preconditioning_weekdays_only"
ATTR_DEPARTURE_TIME = "departure_time"
ATTR_OFF_PEAK_CHARGING_ENABLED = "off_peak_charging_enabled"
ATTR_OFF_PEAK_CHARGING_WEEKDAYS = "off_peak_charging_weekdays_only"
ATTR_END_OFF_PEAK_TIME = "end_off_peak_time"

SERVICE_SET_SCHEDULED_CHARGING = "set_scheduled_charging"
SERVICE_SET_SCHEDULED_DEPARTURE = "set_scheduled_departure"


def async_get_device_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> dr.DeviceEntry:
    """Get the device entry related to a service call."""
    device_id = call.data[CONF_DEVICE_ID]
    device_registry = dr.async_get(hass)
    if (device_entry := device_registry.async_get(device_id)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device",
            translation_placeholders={"device_id": device_id},
        )

    return device_entry


def async_get_config_for_device(
    hass: HomeAssistant, device_entry: dr.DeviceEntry
) -> ConfigEntry:
    """Get the config entry related to a device entry."""
    for entry_id in device_entry.config_entries:
        if entry := hass.config_entries.async_get_entry(entry_id):
            if entry.domain == DOMAIN:
                return entry
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_device",
        translation_placeholders={"device_id": str(device_entry.id)},
    )


def async_get_vehicle_for_entry(
    device: dr.DeviceEntry, config: ConfigEntry
) -> TessieVehicleData:
    """Get the vehicle data for a config entry."""
    assert device.serial_number is not None
    for vehicle in config.runtime_data.vehicles:
        if vehicle.vin == device.serial_number:
            return vehicle
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_device",
        translation_placeholders={"device_id": str(device.id)},
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Tessie services."""

    async def handle_set_scheduled_charging(call: ServiceCall) -> None:
        """Handle the set_scheduled_charging service call."""
        device = async_get_device_for_service_call(hass, call)
        config = async_get_config_for_device(hass, device)
        vehicle = async_get_vehicle_for_entry(device, config)

        time_mins: int
        if ATTR_TIME in call.data:
            (hours, minutes, *_seconds) = call.data[ATTR_TIME].split(":")
            time_mins = int(hours) * 60 + int(minutes)
        elif call.data[ATTR_ENABLE]:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="set_scheduled_charging_time",
            )
        else:
            time_mins = 0

        try:
            response = await set_scheduled_charging(
                session=vehicle.data_coordinator.session,
                vin=vehicle.vin,
                api_key=vehicle.data_coordinator.api_key,
                timeMins=time_mins,
                enable=call.data[ATTR_ENABLE],
            )
        except TeslaFleetError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"message": e.message},
            ) from e

        if response.get("result") is False:
            reason = response.get("reason", "unknown")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"message": reason},
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCHEDULED_CHARGING,
        handle_set_scheduled_charging,
        schema=vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): cv.string,
                vol.Required(ATTR_ENABLE): bool,
                vol.Optional(ATTR_TIME): str,
            }
        ),
    )

    async def handle_set_scheduled_departure(call: ServiceCall) -> None:
        """Handle the set_scheduled_departure service call."""
        device = async_get_device_for_service_call(hass, call)
        config = async_get_config_for_device(hass, device)
        vehicle = async_get_vehicle_for_entry(device, config)

        enable = call.data.get(ATTR_ENABLE, True)

        preconditioning_enabled = call.data.get(ATTR_PRECONDITIONING_ENABLED, False)
        preconditioning_weekdays_only = call.data.get(
            ATTR_PRECONDITIONING_WEEKDAYS, False
        )

        departure_time_mins: int
        if ATTR_DEPARTURE_TIME in call.data:
            (hours, minutes, *_seconds) = call.data[ATTR_DEPARTURE_TIME].split(":")
            departure_time_mins = int(hours) * 60 + int(minutes)
        elif preconditioning_enabled:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="set_scheduled_departure_preconditioning",
            )
        else:
            departure_time_mins = 0

        off_peak_charging_enabled = call.data.get(ATTR_OFF_PEAK_CHARGING_ENABLED, False)
        off_peak_charging_weekdays_only = call.data.get(
            ATTR_OFF_PEAK_CHARGING_WEEKDAYS, False
        )

        end_off_peak_time_mins: int
        if ATTR_END_OFF_PEAK_TIME in call.data:
            (hours, minutes, *_seconds) = call.data[ATTR_END_OFF_PEAK_TIME].split(":")
            end_off_peak_time_mins = int(hours) * 60 + int(minutes)
        elif off_peak_charging_enabled:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="set_scheduled_departure_off_peak",
            )
        else:
            end_off_peak_time_mins = 0

        try:
            response = await set_scheduled_departure(
                session=vehicle.data_coordinator.session,
                vin=vehicle.vin,
                api_key=vehicle.data_coordinator.api_key,
                departure_time_mins=departure_time_mins,
                end_off_peak_time_mins=end_off_peak_time_mins,
                enable=enable,
                preconditioning_enabled=preconditioning_enabled,
                preconditioning_weekdays_only=preconditioning_weekdays_only,
                off_peak_charging_enabled=off_peak_charging_enabled,
                off_peak_charging_weekdays_only=off_peak_charging_weekdays_only,
            )
        except TeslaFleetError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"message": e.message},
            ) from e

        if response.get("result") is False:
            reason = response.get("reason", "unknown")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"message": reason},
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCHEDULED_DEPARTURE,
        handle_set_scheduled_departure,
        schema=vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): cv.string,
                vol.Optional(ATTR_ENABLE): bool,
                vol.Optional(ATTR_PRECONDITIONING_ENABLED): bool,
                vol.Optional(ATTR_PRECONDITIONING_WEEKDAYS): bool,
                vol.Optional(ATTR_DEPARTURE_TIME): str,
                vol.Optional(ATTR_OFF_PEAK_CHARGING_ENABLED): bool,
                vol.Optional(ATTR_OFF_PEAK_CHARGING_WEEKDAYS): bool,
                vol.Optional(ATTR_END_OFF_PEAK_TIME): str,
            }
        ),
    )
