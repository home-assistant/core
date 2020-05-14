"""The denonavr component."""
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send

DOMAIN = "denonavr"

SERVICE_GET_COMMAND = "get_command"
ATTR_COMMAND = "command"

CALL_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids})

GET_COMMAND_SCHEMA = CALL_SCHEMA.extend({vol.Required(ATTR_COMMAND): cv.string})

SERVICE_TO_METHOD = {
    SERVICE_GET_COMMAND: {"method": "get_command", "schema": GET_COMMAND_SCHEMA}
}


def setup(hass, config):
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
