"""The denonavr component."""
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_MAC, CONF_TIMEOUT
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import dispatcher_send

from .config_flow import (
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SHOW_ALL_SOURCES,
    CONF_TYPE,
    CONF_ZONE2,
    CONF_ZONE3,
    DOMAIN,
)
from .receiver import ConnectDenonAVR

SERVICE_GET_COMMAND = "get_command"
ATTR_COMMAND = "command"

CALL_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids})

GET_COMMAND_SCHEMA = CALL_SCHEMA.extend({vol.Required(ATTR_COMMAND): cv.string})

SERVICE_TO_METHOD = {
    SERVICE_GET_COMMAND: {"method": "get_command", "schema": GET_COMMAND_SCHEMA}
}


def setup(hass: core.HomeAssistant, config: dict):
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
    """Set up the denonavr components from a config entry."""
    if hass.data.get(DOMAIN) is None:
        hass.data[DOMAIN] = {}

    # Connect to receiver
    connect_denonavr = ConnectDenonAVR(
        hass,
        entry.data[CONF_HOST],
        entry.data[CONF_TIMEOUT],
        entry.data[CONF_SHOW_ALL_SOURCES],
        entry.data[CONF_ZONE2],
        entry.data[CONF_ZONE3],
    )
    await connect_denonavr.async_connect_receiver()
    receiver = connect_denonavr.receiver

    hass.data[DOMAIN][entry.entry_id] = receiver

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, entry.data[CONF_MAC])},
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer=entry.data[CONF_MANUFACTURER],
        name=entry.title,
        model=f"{entry.data[CONF_MODEL]}-{entry.data[CONF_TYPE]}",
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(
        entry, "media_player"
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
