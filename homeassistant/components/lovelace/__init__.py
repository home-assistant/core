"""Lovelace UI."""
import sys
import uuid
import voluptuous as vol
from collections import OrderedDict
from typing import Union, List, Dict, Iterator, overload, TypeVar

from homeassistant.components import websocket_api
from homeassistant.exceptions import HomeAssistantError

DOMAIN = 'lovelace'
REQUIREMENTS = ['ruamel.yaml==0.15.72']

OLD_WS_TYPE_GET_LOVELACE_UI = 'frontend/lovelace_config'
WS_TYPE_GET_LOVELACE_UI = 'lovelace/config'

SCHEMA_GET_LOVELACE_UI = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): vol.Any(WS_TYPE_GET_LOVELACE_UI,
                                  OLD_WS_TYPE_GET_LOVELACE_UI),
})

JSON_TYPE = Union[List, Dict, str]  # pylint: disable=invalid-name

def save_yaml(fname, data):
    from ruamel.yaml import YAML
    """Save a YAML file."""
    yaml = YAML()
    yaml.explicit_start = True
    yaml.indent(sequence=4, offset=2)
    try:
        with open(fname, "w", encoding='utf-8') as conf_file:
            yaml.dump(data, conf_file)
    except YAMLError as exc:
        _LOGGER.error(str(exc))
        raise HomeAssistantError(exc)

def load_yaml(fname: str) -> JSON_TYPE:
    from ruamel.yaml import YAML
    """Load a YAML file."""
    yaml = YAML()
    try:
        with open(fname, encoding='utf-8') as conf_file:
            # If configuration file is empty YAML returns None
            # We convert that to an empty dict
            return yaml.load(conf_file) or OrderedDict()
    except YAMLError as exc:
        _LOGGER.error(str(exc))
        raise HomeAssistantError(exc)
    except UnicodeDecodeError as exc:
        _LOGGER.error("Unable to read file %s: %s", fname, exc)
        raise HomeAssistantError(exc)

def load_config(fname: str) -> JSON_TYPE:
    config = load_yaml(fname)
    # Check if all cards have an ID or else add one
    updated = False
    views = config.get('views')
    if views:
        for view in views:
            if 'cards' in view:
                for card in view.get('cards'):
                    if 'id' not in card:
                        updated = True
                        card['id'] = uuid.uuid4().hex
                        card.move_to_end('id', last=False)
    if updated:
        save_yaml(fname, config);
    return config;

async def async_setup(hass, config):
    """Set up the Lovelace commands."""
    # Backwards compat. Added in 0.80. Remove after 0.85
    hass.components.websocket_api.async_register_command(
        OLD_WS_TYPE_GET_LOVELACE_UI, websocket_lovelace_config,
        SCHEMA_GET_LOVELACE_UI)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_GET_LOVELACE_UI, websocket_lovelace_config,
        SCHEMA_GET_LOVELACE_UI)

    return True


@websocket_api.async_response
async def websocket_lovelace_config(hass, connection, msg):
    """Send lovelace UI config over websocket config."""
    error = None
    try:
        config = await hass.async_add_executor_job(
            load_config, hass.config.path('ui-lovelace.yaml'))
        message = websocket_api.result_message(
            msg['id'], config
        )
    except FileNotFoundError:
        error = ('file_not_found',
                 'Could not find ui-lovelace.yaml in your config dir.')
    except HomeAssistantError as err:
        error = 'load_error', str(err)

    if error is not None:
        message = websocket_api.error_message(msg['id'], *error)

    connection.send_message(message)
