"""Service calls for the Tesla Fleet integration."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .helpers import handle_command
from .models import TeslaFleetEnergyData

_LOGGER = logging.getLogger(__name__)

# Attributes
ATTR_TOU_SETTINGS = "tou_settings"

# Services
SERVICE_TIME_OF_USE = "time_of_use"


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
    config_entry: ConfigEntry
    for entry_id in device_entry.config_entries:
        if entry := hass.config_entries.async_get_entry(entry_id):
            if entry.domain == DOMAIN:
                config_entry = entry
    return config_entry


def async_get_energy_site_for_entry(
    hass: HomeAssistant, device: dr.DeviceEntry, config: ConfigEntry
) -> TeslaFleetEnergyData:
    """Get the energy site data for a config entry."""
    energy_data: TeslaFleetEnergyData
    assert device.serial_number is not None
    for energysite in config.runtime_data.energysites:
        if str(energysite.id) == device.serial_number:
            energy_data = energysite
    return energy_data


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Tesla Fleet services."""

    async def time_of_use(call: ServiceCall) -> None:
        """Configure time-of-use settings on an energy site.

        Wraps the Tesla Fleet API
        ``POST /api/1/energy_sites/{site_id}/time_of_use_settings`` endpoint.
        Pass the ``tariff_content_v2`` payload as ``tou_settings``; the
        outer ``tariff_content_v2`` wrapper is stripped automatically if
        present.
        """
        device = async_get_device_for_service_call(hass, call)
        config = async_get_config_for_device(hass, device)
        site = async_get_energy_site_for_entry(hass, device, config)

        tou_settings = call.data[ATTR_TOU_SETTINGS]
        # Unwrap tariff_content_v2 if user included it, since the SDK adds
        # this wrapper itself.
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
        SERVICE_TIME_OF_USE,
        time_of_use,
        schema=vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): cv.string,
                vol.Required(ATTR_TOU_SETTINGS): dict,
            }
        ),
        description_placeholders={
            "time_of_use_url": (
                "https://developer.tesla.com/docs/fleet-api#time_of_use_settings"
            )
        },
    )
