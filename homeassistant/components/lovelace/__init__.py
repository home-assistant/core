"""Lovelace UI."""
import logging
import uuid
import os
from os import O_CREAT, O_TRUNC, O_WRONLY
from collections import OrderedDict
from typing import Dict, List, Union

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'lovelace'
REQUIREMENTS = ['ruamel.yaml==0.15.72']

LOVELACE_CONFIG_FILE = 'ui-lovelace.yaml'
JSON_TYPE = Union[List, Dict, str]  # pylint: disable=invalid-name

FORMAT_YAML = 'yaml'
FORMAT_JSON = 'json'

OLD_WS_TYPE_GET_LOVELACE_UI = 'frontend/lovelace_config'
WS_TYPE_GET_LOVELACE_UI = 'lovelace/config'

WS_TYPE_MIGRATE_CONFIG = 'lovelace/config/migrate'
WS_TYPE_GET_CARD = 'lovelace/config/card/get'
WS_TYPE_UPDATE_CARD = 'lovelace/config/card/update'
WS_TYPE_ADD_CARD = 'lovelace/config/card/add'

SCHEMA_GET_LOVELACE_UI = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): vol.Any(WS_TYPE_GET_LOVELACE_UI,
                                  OLD_WS_TYPE_GET_LOVELACE_UI),
})

SCHEMA_MIGRATE_CONFIG = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_MIGRATE_CONFIG,
})

SCHEMA_GET_CARD = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_GET_CARD,
    vol.Required('card_id'): str,
    vol.Optional('format', default=FORMAT_YAML): vol.Any(FORMAT_JSON,
                                                         FORMAT_YAML),
})

SCHEMA_UPDATE_CARD = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_UPDATE_CARD,
    vol.Required('card_id'): str,
    vol.Required('card_config'): vol.Any(str, Dict),
    vol.Optional('format', default=FORMAT_YAML): vol.Any(FORMAT_JSON,
                                                         FORMAT_YAML),
})

SCHEMA_ADD_CARD = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_ADD_CARD,
    vol.Required('view_id'): str,
    vol.Required('card_config'): vol.Any(str, Dict),
    vol.Optional('position'): int,
    vol.Optional('format', default=FORMAT_YAML): vol.Any(FORMAT_JSON,
                                                         FORMAT_YAML),
})


class WriteError(HomeAssistantError):
    """Error writing the data."""


class CardNotFoundError(HomeAssistantError):
    """Card not found in data."""


class ViewNotFoundError(HomeAssistantError):
    """View not found in data."""


class UnsupportedYamlError(HomeAssistantError):
    """Unsupported YAML."""


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


def _yaml_unsupported(loader, node):
    raise UnsupportedYamlError(
        'Unsupported YAML, you can not use {} in ui-lovelace.yaml'
        .format(node.tag))


def load_yaml(fname: str) -> JSON_TYPE:
    """Load a YAML file."""
    from ruamel.yaml import YAML
    from ruamel.yaml.constructor import RoundTripConstructor
    from ruamel.yaml.error import YAMLError

    RoundTripConstructor.add_constructor(None, _yaml_unsupported)

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
    """Load a YAML file."""
    return load_yaml(fname)


def migrate_config(fname: str) -> JSON_TYPE:
    """Load a YAML file and adds id to views and cards if not present."""
    config = load_yaml(fname)
    # Check if all views and cards have an id or else add one
    updated = False
    index = 0
    for view in config.get('views', []):
        if 'id' not in view:
            updated = True
            view.insert(0, 'id', index,
                        comment="Automatically created id")
        for card in view.get('cards', []):
            if 'id' not in card:
                updated = True
                card.insert(0, 'id', uuid.uuid4().hex,
                            comment="Automatically created id")
        index += 1
    if updated:
        save_yaml(fname, config)
    return config


def object_to_yaml(data: JSON_TYPE) -> str:
    """Create yaml string from object."""
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
    """Create object from yaml string."""
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError
    yaml = YAML(typ='rt')
    try:
        return yaml.load(data)
    except YAMLError as exc:
        _LOGGER.error("YAML error: %s", exc)
        raise HomeAssistantError(exc)


def get_card(fname: str, card_id: str, data_format: str = FORMAT_YAML)\
        -> JSON_TYPE:
    """Load a specific card config for id."""
    config = load_yaml(fname)
    for view in config.get('views', []):
        for card in view.get('cards', []):
            if card.get('id') != card_id:
                continue
            if data_format == FORMAT_YAML:
                return object_to_yaml(card)
            return card

    raise CardNotFoundError(
        "Card with ID: {} was not found in {}.".format(card_id, fname))


def update_card(fname: str, card_id: str, card_config: str,
                data_format: str = FORMAT_YAML):
    """Save a specific card config for id."""
    config = load_yaml(fname)
    for view in config.get('views', []):
        for card in view.get('cards', []):
            if card.get('id') != card_id:
                continue
            if data_format == FORMAT_YAML:
                card_config = yaml_to_object(card_config)
            card.update(card_config)
            save_yaml(fname, config)
            return

    raise CardNotFoundError(
        "Card with ID: {} was not found in {}.".format(card_id, fname))


def add_card(fname: str, view_id: str, card_config: str,
             position: int = None, data_format: str = FORMAT_YAML):
    """Add a card to a view."""
    config = load_yaml(fname)
    for view in config.get('views', []):
        if view.get('id') != view_id:
            continue
        cards = view.get('cards', [])
        if data_format == FORMAT_YAML:
            card_config = yaml_to_object(card_config)
        if position is None:
            cards.append(card_config)
        else:
            cards.insert(position, card_config)
        save_yaml(fname, config)
        return

    raise ViewNotFoundError(
        "View with ID: {} was not found in {}.".format(view_id, fname))


async def async_setup(hass, config):
    """Set up the Lovelace commands."""
    # Backwards compat. Added in 0.80. Remove after 0.85
    hass.components.websocket_api.async_register_command(
        OLD_WS_TYPE_GET_LOVELACE_UI, websocket_lovelace_config,
        SCHEMA_GET_LOVELACE_UI)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_MIGRATE_CONFIG, websocket_lovelace_migrate_config,
        SCHEMA_MIGRATE_CONFIG)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_GET_LOVELACE_UI, websocket_lovelace_config,
        SCHEMA_GET_LOVELACE_UI)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_GET_CARD, websocket_lovelace_get_card,
        SCHEMA_GET_CARD)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_UPDATE_CARD, websocket_lovelace_update_card,
        SCHEMA_UPDATE_CARD)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_ADD_CARD, websocket_lovelace_add_card,
        SCHEMA_ADD_CARD)

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
    except UnsupportedYamlError as err:
        error = 'unsupported_error', str(err)
    except HomeAssistantError as err:
        error = 'load_error', str(err)

    if error is not None:
        message = websocket_api.error_message(msg['id'], *error)

    connection.send_message(message)


@websocket_api.async_response
async def websocket_lovelace_migrate_config(hass, connection, msg):
    """Migrate lovelace UI config."""
    error = None
    try:
        config = await hass.async_add_executor_job(
            migrate_config, hass.config.path(LOVELACE_CONFIG_FILE))
        message = websocket_api.result_message(
            msg['id'], config
        )
    except FileNotFoundError:
        error = ('file_not_found',
                 'Could not find ui-lovelace.yaml in your config dir.')
    except UnsupportedYamlError as err:
        error = 'unsupported_error', str(err)
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
            get_card, hass.config.path(LOVELACE_CONFIG_FILE), msg['card_id'],
            msg.get('format', FORMAT_YAML))
        message = websocket_api.result_message(
            msg['id'], card
        )
    except FileNotFoundError:
        error = ('file_not_found',
                 'Could not find ui-lovelace.yaml in your config dir.')
    except UnsupportedYamlError as err:
        error = 'unsupported_error', str(err)
    except CardNotFoundError as err:
        error = 'card_not_found', str(err)
    except HomeAssistantError as err:
        error = 'load_error', str(err)

    if error is not None:
        message = websocket_api.error_message(msg['id'], *error)

    connection.send_message(message)


@websocket_api.async_response
async def websocket_lovelace_update_card(hass, connection, msg):
    """Receive lovelace card config over websocket and save."""
    error = None
    try:
        await hass.async_add_executor_job(
            update_card, hass.config.path(LOVELACE_CONFIG_FILE),
            msg['card_id'], msg['card_config'], msg.get('format', FORMAT_YAML))
        message = websocket_api.result_message(
            msg['id'], True
        )
    except FileNotFoundError:
        error = ('file_not_found',
                 'Could not find ui-lovelace.yaml in your config dir.')
    except UnsupportedYamlError as err:
        error = 'unsupported_error', str(err)
    except CardNotFoundError as err:
        error = 'card_not_found', str(err)
    except HomeAssistantError as err:
        error = 'save_error', str(err)

    if error is not None:
        message = websocket_api.error_message(msg['id'], *error)

    connection.send_message(message)


@websocket_api.async_response
async def websocket_lovelace_add_card(hass, connection, msg):
    """Add new card to view over websocket and save."""
    error = None
    try:
        await hass.async_add_executor_job(
            add_card, hass.config.path(LOVELACE_CONFIG_FILE),
            msg['view_id'], msg['card_config'], msg.get('position'),
            msg.get('format', FORMAT_YAML))
        message = websocket_api.result_message(
            msg['id'], True
        )
    except FileNotFoundError:
        error = ('file_not_found',
                 'Could not find ui-lovelace.yaml in your config dir.')
    except UnsupportedYamlError as err:
        error = 'unsupported_error', str(err)
    except ViewNotFoundError as err:
        error = 'view_not_found', str(err)
    except HomeAssistantError as err:
        error = 'save_error', str(err)

    if error is not None:
        message = websocket_api.error_message(msg['id'], *error)

    connection.send_message(message)
