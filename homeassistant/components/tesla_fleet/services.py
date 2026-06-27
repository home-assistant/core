"""Service calls for the Tesla Fleet integration."""

from tesla_fleet_api.const import Scope
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .helpers import handle_command
from .models import TeslaFleetEnergyData

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
    for entry_id in device_entry.config_entries:
        entry = hass.config_entries.async_get_known_entry(entry_id)
        if entry.domain == DOMAIN:
            if entry.state is not ConfigEntryState.LOADED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="entry_not_loaded",
                )
            return entry
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_device",
        translation_placeholders={"device_id": device_entry.id},
    )


def async_get_energy_site_for_entry(
    hass: HomeAssistant, device: dr.DeviceEntry, config: ConfigEntry
) -> TeslaFleetEnergyData:
    """Get the energy site data for a config entry."""
    for energysite in config.runtime_data.energysites:
        if str(energysite.id) == device.serial_number:
            return energysite
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_device",
        translation_placeholders={"device_id": device.id},
    )


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
        if Scope.ENERGY_CMDS not in config.runtime_data.scopes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="missing_scope_energy_cmds",
            )

        tou_settings = call.data[ATTR_TOU_SETTINGS]
        # Unwrap tariff_content_v2 if user included it, since the SDK adds
        # this wrapper itself.
        if "tariff_content_v2" in tou_settings:
            tou_settings = tou_settings["tariff_content_v2"]

        resp = await handle_command(site.api.time_of_use_settings(tou_settings))
        if error := resp.get("error"):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_error",
                translation_placeholders={"error": error},
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
