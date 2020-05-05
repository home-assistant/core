"""The denonavr component."""
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_TIMEOUT
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import dispatcher_send

from .config_flow import CONF_RECEIVER_ID, CONF_SHOW_ALL_SOURCES, CONF_ZONE2, CONF_ZONE3, DOMAIN
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
    if not await connect_denonavr.async_connect_receiver():
        return False
    receiver = connect_denonavr.receiver

    hass.data[DOMAIN][entry.entry_id] = receiver

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.data[CONF_RECEIVER_ID])},
        manufacturer=receiver.manufacturer,
        name=receiver.name,
        model=f"{receiver.model_name}-{receiver.receiver_type}",
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )

    return True
