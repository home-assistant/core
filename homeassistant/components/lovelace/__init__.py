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

LOVELACE_CONFIG_FILE = 'ui-lovelace.yaml'
JSON_TYPE = Union[List, Dict, str]  # pylint: disable=invalid-name

OLD_WS_TYPE_GET_LOVELACE_UI = 'frontend/lovelace_config'
WS_TYPE_GET_LOVELACE_UI = 'lovelace/config'
WS_TYPE_GET_CARD = 'lovelace/config/card/get'
WS_TYPE_SET_CARD = 'lovelace/config/card/set'

SCHEMA_GET_LOVELACE_UI = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): vol.Any(WS_TYPE_GET_LOVELACE_UI,
                                  OLD_WS_TYPE_GET_LOVELACE_UI),
})

SCHEMA_GET_CARD = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_GET_CARD,
    vol.Required('card_id'): str,
})

SCHEMA_SET_CARD = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_SET_CARD,
    vol.Required('card_id'): str,
    vol.Required('card_config'): str,
})


class WriteError(HomeAssistantError):
    """Error writing the data."""


class CardNotFoundError(HomeAssistantError):
    """Card not found in data."""


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
        _LOGGER.exception('Saving YAML file %s failed: %s', fname, exc)
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
        _LOGGER.error("YAML error in %s: %s", fname, exc)
        raise HomeAssistantError(exc)
    except UnicodeDecodeError as exc:
        _LOGGER.error("Unable to read file %s: %s", fname, exc)
        raise HomeAssistantError(exc)


def load_config(fname: str) -> JSON_TYPE:
    """Load a YAML file and adds id to views and cards if not present."""
    config = load_yaml(fname)
    # Check if all views and cards have an id or else add one
    updated = False
    index = 0
    for view in config.get('views', []):
        if 'id' not in view:
            updated = True
            view['id'] = index
            view.move_to_end('id', last=False)
        for card in view.get('cards', []):
            if 'id' not in card:
                updated = True
                card['id'] = uuid.uuid4().hex
                card.move_to_end('id', last=False)
        index += 1
    if updated:
        save_yaml(fname, config)
    return config


def object_to_yaml(data: JSON_TYPE) -> str:
    """create yaml string from object."""
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError
    from ruamel.yaml.compat import StringIO
    yaml = YAML(typ='rt')
    yaml.indent(sequence=4, offset=2)
    stream = StringIO()
    try:
        yaml.dump(data, stream)
        return stream.getvalue()
    except YAMLError as exc:
        _LOGGER.error("YAML error: %s", exc)
        raise HomeAssistantError(exc)


def yaml_to_object(data: str) -> JSON_TYPE:
    """create object from yaml string."""
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError
    yaml = YAML(typ='rt')
    yaml.preserve_quotes = True
    try:
        return yaml.load(data)
    except YAMLError as exc:
        _LOGGER.error("YAML error: %s", exc)
        raise HomeAssistantError(exc)


def get_card(fname: str, card_id: str) -> JSON_TYPE:
    """Load a specific card config for id."""
    config = load_yaml(fname)
    for view in config.get('views', []):
        for card in view.get('cards', []):
            if card.get('id') == card_id:
                return object_to_yaml(card)

    raise CardNotFoundError("Card with ID: {} was not found in {}.".format(card_id, fname))


def set_card(fname: str, card_id: str, card_config: str) -> bool:
    """Save a specific card config for id."""
    config = load_yaml(fname)
    for view in config.get('views', []):
        for card in view.get('cards', []):
            if card.get('id') == card_id:
                card.update(yaml_to_object(card_config))
                save_yaml(fname, config)
                # Do we want to return config on save?
                return True

    raise CardNotFoundError("Card with ID: {} was not found in {}.".format(card_id, fname))


async def async_setup(hass, config):
    """Set up the Lovelace commands."""
    # Backwards compat. Added in 0.80. Remove after 0.85
    hass.components.websocket_api.async_register_command(
        OLD_WS_TYPE_GET_LOVELACE_UI, websocket_lovelace_config,
        SCHEMA_GET_LOVELACE_UI)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_GET_LOVELACE_UI, websocket_lovelace_config,
        SCHEMA_GET_LOVELACE_UI)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_GET_CARD, websocket_lovelace_get_card,
        SCHEMA_GET_CARD)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_SET_CARD, websocket_lovelace_set_card,
        SCHEMA_SET_CARD)

    return True


@websocket_api.async_response
async def websocket_lovelace_config(hass, connection, msg):
    """Send lovelace UI config over websocket config."""
    error = None
    try:
        config = await hass.async_add_executor_job(
            load_config, hass.config.path(LOVELACE_CONFIG_FILE))
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


@websocket_api.async_response
async def websocket_lovelace_get_card(hass, connection, msg):
    """Send lovelace card config over websocket config."""
    error = None
    try:
        card = await hass.async_add_executor_job(
            get_card, hass.config.path(LOVELACE_CONFIG_FILE), msg['card_id'])
        message = websocket_api.result_message(
            msg['id'], card
        )
    except FileNotFoundError:
        error = ('file_not_found',
                 'Could not find ui-lovelace.yaml in your config dir.')
    except CardNotFoundError:
        error = ('card_not_found',
                 'Could not find card in ui-lovelace.yaml.')
    except HomeAssistantError as err:
        error = 'load_error', str(err)

    if error is not None:
        message = websocket_api.error_message(msg['id'], *error)

    connection.send_message(message)


@websocket_api.async_response
async def websocket_lovelace_set_card(hass, connection, msg):
    """Receive lovelace card config over websocket and save."""
    error = None
    try:
        result = await hass.async_add_executor_job(
            set_card, hass.config.path(LOVELACE_CONFIG_FILE), 
            msg['card_id'], msg['card_config'])
        message = websocket_api.result_message(
            msg['id'], result
        )
    except FileNotFoundError:
        error = ('file_not_found',
                 'Could not find ui-lovelace.yaml in your config dir.')
    except CardNotFoundError:
        error = ('card_not_found',
                 'Could not find card in ui-lovelace.yaml.')
    except HomeAssistantError as err:
        error = 'save_error', str(err)

    if error is not None:
        message = websocket_api.error_message(msg['id'], *error)

    connection.send_message(message)
