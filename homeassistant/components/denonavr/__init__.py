"""The denonavr component."""
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL
import homeassistant.helpers.config_validation as cv

DOMAIN = "denonavr"

SERVICE_GET_COMMAND = "get_command"
ATTR_COMMAND = "command"

CALL_SCHEMA = vol.Schema({ATTR_ENTITY_ID: cv.comp_entity_ids})

GET_COMMAND_SCHEMA = CALL_SCHEMA.extend({vol.Required(ATTR_COMMAND): cv.string})

SERVICE_TO_METHOD = {
    SERVICE_GET_COMMAND: {"method": "get_command", "schema": GET_COMMAND_SCHEMA}
}


def setup(hass, config):
    """Set up the denonavr platform."""
    hass.data[DOMAIN] = {}

    def service_handler(service):
        method = SERVICE_TO_METHOD.get(service.service)
        params = {
            key: value for key, value in service.data.items() if key != "entity_id"
        }
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        target_players = []
        for player in hass.data[DOMAIN]["receivers"]:
            if entity_ids == ENTITY_MATCH_ALL or player.entity_id in entity_ids:
                target_players.append(player)

        for player in target_players:
            getattr(player, method["method"])(**params)

    for service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service]["schema"]
        hass.services.register(DOMAIN, service, service_handler, schema=schema)

    return True
