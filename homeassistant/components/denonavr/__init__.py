"""The denonavr component."""
import voluptuous as vol

import denonavr

from homeassistant import config_entries, core
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_TIMEOUT
from homeassistant.helpers import device_registry as dr, config_validation as cv, dispatcher_send

from .config_flow import DOMAIN, CONF_SHOW_ALL_SOURCES, CONF_ZONE2, CONF_ZONE3


SERVICE_GET_COMMAND = "get_command"
ATTR_COMMAND = "command"

CALL_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids})

GET_COMMAND_SCHEMA = CALL_SCHEMA.extend({vol.Required(ATTR_COMMAND): cv.string})

SERVICE_TO_METHOD = {
    SERVICE_GET_COMMAND: {"method": "get_command", "schema": GET_COMMAND_SCHEMA}
}


def async_setup(hass: core.HomeAssistant, config: dict):
    """Set up the denonavr platform."""

    def service_handler(service):
        method = SERVICE_TO_METHOD.get(service.service)
        data = service.data.copy()
        data["method"] = method["method"]
        dispatcher_send(hass, DOMAIN, data)

    for service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service]["schema"]
        hass.services.register(DOMAIN, service, service_handler, schema=schema)

    return True

async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Set up the Xiaomi Miio components from a config entry."""
    hass.data[DOMAIN] = {}

    zones = {}
    if entry.data[CONF_ZONE2]:
        zones["Zone2"] = None
    if entry.data[CONF_ZONE3]:
        zones["Zone3"] = None

    # Connect to reciever
    receiver = denonavr.DenonAVR(
        host=entry.data[CONF_HOST],
        show_all_inputs=entry.data[CONF_SHOW_ALL_SOURCES],
        timeout=entry.data[CONF_TIMEOUT],
        add_zones=zones,
    )

    hass.data[DOMAIN][entry.entry_id] = receiver

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.data["receiver_id"])},
        manufacturer=reciever.manufacturer,
        name=reciever.name,
        model=reciever.model_name,
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )

    return True