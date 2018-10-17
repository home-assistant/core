"""Lovelace UI."""
import logging
import uuid
import os
from os import O_WRONLY, O_CREAT, O_TRUNC
from collections import OrderedDict
from typing import Union, List, Dict
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'lovelace'
REQUIREMENTS = ['ruamel.yaml==0.15.72']

OLD_WS_TYPE_GET_LOVELACE_UI = 'frontend/lovelace_config'
WS_TYPE_GET_LOVELACE_UI = 'lovelace/config'

SCHEMA_GET_LOVELACE_UI = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): vol.Any(WS_TYPE_GET_LOVELACE_UI,
                                  OLD_WS_TYPE_GET_LOVELACE_UI),
})

JSON_TYPE = Union[List, Dict, str]  # pylint: disable=invalid-name


class WriteError(HomeAssistantError):
    """Error writing the data."""


def save_yaml(fname: str, data: JSON_TYPE):
    """Save a YAML file."""
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError
    yaml = YAML(typ='rt')
    yaml.indent(sequence=4, offset=2)
    tmp_fname = fname + "__TEMP__"
    try:
        with open(os.open(tmp_fname, O_WRONLY | O_CREAT | O_TRUNC, 0o644),
                  'w', encoding='utf-8') as temp_file:
            yaml.dump(data, temp_file)
        os.replace(tmp_fname, fname)
    except YAMLError as exc:
        _LOGGER.error(str(exc))
        raise HomeAssistantError(exc)
    except OSError as exc:
        _LOGGER.exception('Saving YAML file failed: %s', fname)
        raise WriteError(exc)
    finally:
        if os.path.exists(tmp_fname):
            try:
                os.remove(tmp_fname)
            except OSError as exc:
                # If we are cleaning up then something else went wrong, so
                # we should suppress likely follow-on errors in the cleanup
                _LOGGER.error("YAML replacement cleanup failed: %s", exc)


def load_yaml(fname: str) -> JSON_TYPE:
    """Load a YAML file."""
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError
    yaml = YAML(typ='rt')
    try:
        with open(fname, encoding='utf-8') as conf_file:
            # If configuration file is empty YAML returns None
            # We convert that to an empty dict
            return yaml.load(conf_file) or OrderedDict()
    except YAMLError as exc:
        _LOGGER.error("YAML error: %s", exc)
        raise HomeAssistantError(exc)
    except UnicodeDecodeError as exc:
        _LOGGER.error("Unable to read file %s: %s", fname, exc)
        raise HomeAssistantError(exc)


def load_config(fname: str) -> JSON_TYPE:
    """Load a YAML file and adds id to card if not present."""
    config = load_yaml(fname)
    # Check if all cards have an ID or else add one
    updated = False
    for view in config.get('views', []):
        for card in view.get('cards', []):
            if 'id' not in card:
                updated = True
                card['id'] = uuid.uuid4().hex
                card.move_to_end('id', last=False)
    if updated:
        save_yaml(fname, config)
    return config


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
