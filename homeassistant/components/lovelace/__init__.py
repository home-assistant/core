"""
Support for the Lovelace UI.

For more details about this component, please refer to the documentation
at https://www.home-assistant.io/lovelace/
"""
from functools import wraps
import logging
import os
from typing import Dict, List, Union
import time
import uuid

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.ruamel_yaml as yaml

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'lovelace'
LOVELACE_DATA = 'lovelace'

LOVELACE_CONFIG_FILE = 'ui-lovelace.yaml'
JSON_TYPE = Union[List, Dict, str]  # pylint: disable=invalid-name

FORMAT_YAML = 'yaml'
FORMAT_JSON = 'json'

OLD_WS_TYPE_GET_LOVELACE_UI = 'frontend/lovelace_config'
WS_TYPE_GET_LOVELACE_UI = 'lovelace/config'
WS_TYPE_MIGRATE_CONFIG = 'lovelace/config/migrate'
WS_TYPE_SAVE_CONFIG = 'lovelace/config/save'

WS_TYPE_GET_CARD = 'lovelace/config/card/get'
WS_TYPE_UPDATE_CARD = 'lovelace/config/card/update'
WS_TYPE_ADD_CARD = 'lovelace/config/card/add'
WS_TYPE_MOVE_CARD = 'lovelace/config/card/move'
WS_TYPE_DELETE_CARD = 'lovelace/config/card/delete'

WS_TYPE_GET_VIEW = 'lovelace/config/view/get'
WS_TYPE_UPDATE_VIEW = 'lovelace/config/view/update'
WS_TYPE_ADD_VIEW = 'lovelace/config/view/add'
WS_TYPE_MOVE_VIEW = 'lovelace/config/view/move'
WS_TYPE_DELETE_VIEW = 'lovelace/config/view/delete'

SCHEMA_GET_LOVELACE_UI = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'):
        vol.Any(WS_TYPE_GET_LOVELACE_UI, OLD_WS_TYPE_GET_LOVELACE_UI),
    vol.Optional('force', default=False): bool,
})

SCHEMA_MIGRATE_CONFIG = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_MIGRATE_CONFIG,
})

SCHEMA_SAVE_CONFIG = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_SAVE_CONFIG,
    vol.Required('config'): vol.Any(str, dict),
    vol.Optional('format', default=FORMAT_JSON):
        vol.Any(FORMAT_JSON, FORMAT_YAML),
})

SCHEMA_GET_CARD = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_GET_CARD,
    vol.Required('card_id'): str,
    vol.Optional('format', default=FORMAT_YAML):
        vol.Any(FORMAT_JSON, FORMAT_YAML),
})

SCHEMA_UPDATE_CARD = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_UPDATE_CARD,
    vol.Required('card_id'): str,
    vol.Required('card_config'): vol.Any(str, dict),
    vol.Optional('format', default=FORMAT_YAML):
        vol.Any(FORMAT_JSON, FORMAT_YAML),
})

SCHEMA_ADD_CARD = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_ADD_CARD,
    vol.Required('view_id'): str,
    vol.Required('card_config'): vol.Any(str, dict),
    vol.Optional('position'): int,
    vol.Optional('format', default=FORMAT_YAML):
        vol.Any(FORMAT_JSON, FORMAT_YAML),
})

SCHEMA_MOVE_CARD = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_MOVE_CARD,
    vol.Required('card_id'): str,
    vol.Optional('new_position'): int,
    vol.Optional('new_view_id'): str,
})

SCHEMA_DELETE_CARD = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_DELETE_CARD,
    vol.Required('card_id'): str,
})

SCHEMA_GET_VIEW = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_GET_VIEW,
    vol.Required('view_id'): str,
    vol.Optional('format', default=FORMAT_YAML): vol.Any(FORMAT_JSON,
                                                         FORMAT_YAML),
})

SCHEMA_UPDATE_VIEW = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_UPDATE_VIEW,
    vol.Required('view_id'): str,
    vol.Required('view_config'): vol.Any(str, dict),
    vol.Optional('format', default=FORMAT_YAML): vol.Any(FORMAT_JSON,
                                                         FORMAT_YAML),
})

SCHEMA_ADD_VIEW = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_ADD_VIEW,
    vol.Required('view_config'): vol.Any(str, dict),
    vol.Optional('position'): int,
    vol.Optional('format', default=FORMAT_YAML): vol.Any(FORMAT_JSON,
                                                         FORMAT_YAML),
})

SCHEMA_MOVE_VIEW = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_MOVE_VIEW,
    vol.Required('view_id'): str,
    vol.Required('new_position'): int,
})

SCHEMA_DELETE_VIEW = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_DELETE_VIEW,
    vol.Required('view_id'): str,
})


class CardNotFoundError(HomeAssistantError):
    """Card not found in data."""


class ViewNotFoundError(HomeAssistantError):
    """View not found in data."""


class DuplicateIdError(HomeAssistantError):
    """Duplicate ID's."""


def load_config(hass, force: bool) -> JSON_TYPE:
    """Load a YAML file."""
    fname = hass.config.path(LOVELACE_CONFIG_FILE)

    # Check for a cached version of the config
    if not force and LOVELACE_DATA in hass.data:
        config, last_update = hass.data[LOVELACE_DATA]
        modtime = os.path.getmtime(fname)
        if config and last_update > modtime:
            return config

    config = yaml.load_yaml(fname, False)
    seen_card_ids = set()
    seen_view_ids = set()
    if 'views' in config and not isinstance(config['views'], list):
        raise HomeAssistantError("Views should be a list.")
    for view in config.get('views', []):
        if 'id' in view and not isinstance(view['id'], (str, int)):
            raise HomeAssistantError(
                "Your config contains view(s) with invalid ID(s).")
        view_id = str(view.get('id', ''))
        if view_id in seen_view_ids:
            raise DuplicateIdError(
                'ID `{}` has multiple occurances in views'.format(view_id))
        seen_view_ids.add(view_id)
        if 'cards' in view and not isinstance(view['cards'], list):
            raise HomeAssistantError("Cards should be a list.")
        for card in view.get('cards', []):
            if 'id' in card and not isinstance(card['id'], (str, int)):
                raise HomeAssistantError(
                    "Your config contains card(s) with invalid ID(s).")
            card_id = str(card.get('id', ''))
            if card_id in seen_card_ids:
                raise DuplicateIdError(
                    'ID `{}` has multiple occurances in cards'
                    .format(card_id))
            seen_card_ids.add(card_id)
    hass.data[LOVELACE_DATA] = (config, time.time())
    return config


def migrate_config(fname: str) -> None:
    """Add id to views and cards if not present and check duplicates."""
    config = yaml.load_yaml(fname, True)
    updated = False
    seen_card_ids = set()
    seen_view_ids = set()
    index = 0
    for view in config.get('views', []):
        view_id = str(view.get('id', ''))
        if not view_id:
            updated = True
            view.insert(0, 'id', index, comment="Automatically created id")
        else:
            if view_id in seen_view_ids:
                raise DuplicateIdError(
                    'ID `{}` has multiple occurrences in views'.format(
                        view_id))
            seen_view_ids.add(view_id)
        for card in view.get('cards', []):
            card_id = str(card.get('id', ''))
            if not card_id:
                updated = True
                card.insert(0, 'id', uuid.uuid4().hex,
                            comment="Automatically created id")
            else:
                if card_id in seen_card_ids:
                    raise DuplicateIdError(
                        'ID `{}` has multiple occurrences in cards'
                        .format(card_id))
                seen_card_ids.add(card_id)
        index += 1
    if updated:
        yaml.save_yaml(fname, config)


def save_config(fname: str, config, data_format: str = FORMAT_JSON) -> None:
    """Save config to file."""
    if data_format == FORMAT_YAML:
        config = yaml.yaml_to_object(config)
    yaml.save_yaml(fname, config)


def get_card(fname: str, card_id: str, data_format: str = FORMAT_YAML)\
        -> JSON_TYPE:
    """Load a specific card config for id."""
    round_trip = data_format == FORMAT_YAML

    config = yaml.load_yaml(fname, round_trip)

    for view in config.get('views', []):
        for card in view.get('cards', []):
            if str(card.get('id', '')) != card_id:
                continue
            if data_format == FORMAT_YAML:
                return yaml.object_to_yaml(card)
            return card

    raise CardNotFoundError(
        "Card with ID: {} was not found in {}.".format(card_id, fname))


def update_card(fname: str, card_id: str, card_config: str,
                data_format: str = FORMAT_YAML) -> None:
    """Save a specific card config for id."""
    config = yaml.load_yaml(fname, True)
    for view in config.get('views', []):
        for card in view.get('cards', []):
            if str(card.get('id', '')) != card_id:
                continue
            if data_format == FORMAT_YAML:
                card_config = yaml.yaml_to_object(card_config)
            card.clear()
            card.update(card_config)
            yaml.save_yaml(fname, config)
            return

    raise CardNotFoundError(
        "Card with ID: {} was not found in {}.".format(card_id, fname))


def add_card(fname: str, view_id: str, card_config: str,
             position: int = None, data_format: str = FORMAT_YAML) -> None:
    """Add a card to a view."""
    config = yaml.load_yaml(fname, True)
    for view in config.get('views', []):
        if str(view.get('id', '')) != view_id:
            continue
        cards = view.get('cards', [])
        if not cards and 'cards' in view:
            del view['cards']
        if data_format == FORMAT_YAML:
            card_config = yaml.yaml_to_object(card_config)
        if 'id' not in card_config:
            card_config['id'] = uuid.uuid4().hex
        if position is None:
            cards.append(card_config)
        else:
            cards.insert(position, card_config)
        if 'cards' not in view:
            view['cards'] = cards
        yaml.save_yaml(fname, config)
        return

    raise ViewNotFoundError(
        "View with ID: {} was not found in {}.".format(view_id, fname))


def move_card(fname: str, card_id: str, position: int = None) -> None:
    """Move a card to a different position."""
    if position is None:
        raise HomeAssistantError(
            'Position is required if view is not specified.')
    config = yaml.load_yaml(fname, True)
    for view in config.get('views', []):
        for card in view.get('cards', []):
            if str(card.get('id', '')) != card_id:
                continue
            cards = view.get('cards')
            cards.insert(position, cards.pop(cards.index(card)))
            yaml.save_yaml(fname, config)
            return

    raise CardNotFoundError(
        "Card with ID: {} was not found in {}.".format(card_id, fname))


def move_card_view(fname: str, card_id: str, view_id: str,
                   position: int = None) -> None:
    """Move a card to a different view."""
    config = yaml.load_yaml(fname, True)
    for view in config.get('views', []):
        if str(view.get('id', '')) == view_id:
            destination = view.get('cards')
        for card in view.get('cards'):
            if str(card.get('id', '')) != card_id:
                continue
            origin = view.get('cards')
            card_to_move = card

    if 'destination' not in locals():
        raise ViewNotFoundError(
            "View with ID: {} was not found in {}.".format(view_id, fname))
    if 'card_to_move' not in locals():
        raise CardNotFoundError(
            "Card with ID: {} was not found in {}.".format(card_id, fname))

    origin.pop(origin.index(card_to_move))

    if position is None:
        destination.append(card_to_move)
    else:
        destination.insert(position, card_to_move)

    yaml.save_yaml(fname, config)


def delete_card(fname: str, card_id: str) -> None:
    """Delete a card from view."""
    config = yaml.load_yaml(fname, True)
    for view in config.get('views', []):
        for card in view.get('cards', []):
            if str(card.get('id', '')) != card_id:
                continue
            cards = view.get('cards')
            cards.pop(cards.index(card))
            yaml.save_yaml(fname, config)
            return

    raise CardNotFoundError(
        "Card with ID: {} was not found in {}.".format(card_id, fname))


def get_view(fname: str, view_id: str, data_format: str = FORMAT_YAML) -> None:
    """Get view without it's cards."""
    round_trip = data_format == FORMAT_YAML
    config = yaml.load_yaml(fname, round_trip)
    found = None
    for view in config.get('views', []):
        if str(view.get('id', '')) == view_id:
            found = view
            break
    if found is None:
        raise ViewNotFoundError(
            "View with ID: {} was not found in {}.".format(view_id, fname))

    del found['cards']
    if data_format == FORMAT_YAML:
        return yaml.object_to_yaml(found)
    return found


def update_view(fname: str, view_id: str, view_config, data_format:
                str = FORMAT_YAML) -> None:
    """Update view."""
    config = yaml.load_yaml(fname, True)
    found = None
    for view in config.get('views', []):
        if str(view.get('id', '')) == view_id:
            found = view
            break
    if found is None:
        raise ViewNotFoundError(
            "View with ID: {} was not found in {}.".format(view_id, fname))
    if data_format == FORMAT_YAML:
        view_config = yaml.yaml_to_object(view_config)
    if not view_config.get('cards') and found.get('cards'):
        view_config['cards'] = found.get('cards', [])
    if not view_config.get('badges') and found.get('badges'):
        view_config['badges'] = found.get('badges', [])
    found.clear()
    found.update(view_config)
    yaml.save_yaml(fname, config)


def add_view(fname: str, view_config: str,
             position: int = None, data_format: str = FORMAT_YAML) -> None:
    """Add a view."""
    config = yaml.load_yaml(fname, True)
    views = config.get('views', [])
    if data_format == FORMAT_YAML:
        view_config = yaml.yaml_to_object(view_config)
    if 'id' not in view_config:
        view_config['id'] = uuid.uuid4().hex
    if position is None:
        views.append(view_config)
    else:
        views.insert(position, view_config)
    if 'views' not in config:
        config['views'] = views
    yaml.save_yaml(fname, config)


def move_view(fname: str, view_id: str, position: int) -> None:
    """Move a view to a different position."""
    config = yaml.load_yaml(fname, True)
    views = config.get('views', [])
    found = None
    for view in views:
        if str(view.get('id', '')) == view_id:
            found = view
            break
    if found is None:
        raise ViewNotFoundError(
            "View with ID: {} was not found in {}.".format(view_id, fname))

    views.insert(position, views.pop(views.index(found)))
    yaml.save_yaml(fname, config)


def delete_view(fname: str, view_id: str) -> None:
    """Delete a view."""
    config = yaml.load_yaml(fname, True)
    views = config.get('views', [])
    found = None
    for view in views:
        if str(view.get('id', '')) == view_id:
            found = view
            break
    if found is None:
        raise ViewNotFoundError(
            "View with ID: {} was not found in {}.".format(view_id, fname))

    views.pop(views.index(found))
    yaml.save_yaml(fname, config)


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
        WS_TYPE_MIGRATE_CONFIG, websocket_lovelace_migrate_config,
        SCHEMA_MIGRATE_CONFIG)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_SAVE_CONFIG, websocket_lovelace_save_config,
        SCHEMA_SAVE_CONFIG)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_GET_CARD, websocket_lovelace_get_card, SCHEMA_GET_CARD)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_UPDATE_CARD, websocket_lovelace_update_card,
        SCHEMA_UPDATE_CARD)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_ADD_CARD, websocket_lovelace_add_card, SCHEMA_ADD_CARD)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_MOVE_CARD, websocket_lovelace_move_card, SCHEMA_MOVE_CARD)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_DELETE_CARD, websocket_lovelace_delete_card,
        SCHEMA_DELETE_CARD)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_GET_VIEW, websocket_lovelace_get_view, SCHEMA_GET_VIEW)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_UPDATE_VIEW, websocket_lovelace_update_view,
        SCHEMA_UPDATE_VIEW)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_ADD_VIEW, websocket_lovelace_add_view, SCHEMA_ADD_VIEW)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_MOVE_VIEW, websocket_lovelace_move_view, SCHEMA_MOVE_VIEW)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_DELETE_VIEW, websocket_lovelace_delete_view,
        SCHEMA_DELETE_VIEW)

    return True


def handle_yaml_errors(func):
    """Handle error with WebSocket calls."""
    @wraps(func)
    async def send_with_error_handling(hass, connection, msg):
        error = None
        try:
            result = await func(hass, connection, msg)
            message = websocket_api.result_message(
                msg['id'], result
            )
        except FileNotFoundError:
            error = ('file_not_found',
                     'Could not find ui-lovelace.yaml in your config dir.')
        except yaml.UnsupportedYamlError as err:
            error = 'unsupported_error', str(err)
        except yaml.WriteError as err:
            error = 'write_error', str(err)
        except DuplicateIdError as err:
            error = 'duplicate_id', str(err)
        except CardNotFoundError as err:
            error = 'card_not_found', str(err)
        except ViewNotFoundError as err:
            error = 'view_not_found', str(err)
        except HomeAssistantError as err:
            error = 'error', str(err)

        if error is not None:
            message = websocket_api.error_message(msg['id'], *error)

        connection.send_message(message)

    return send_with_error_handling


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_config(hass, connection, msg):
    """Send Lovelace UI config over WebSocket configuration."""
    return await hass.async_add_executor_job(load_config, hass,
                                             msg.get('force', False))


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_migrate_config(hass, connection, msg):
    """Migrate Lovelace UI configuration."""
    return await hass.async_add_executor_job(
        migrate_config, hass.config.path(LOVELACE_CONFIG_FILE))


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_save_config(hass, connection, msg):
    """Save Lovelace UI configuration."""
    return await hass.async_add_executor_job(
        save_config, hass.config.path(LOVELACE_CONFIG_FILE), msg['config'],
        msg.get('format', FORMAT_JSON))


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_get_card(hass, connection, msg):
    """Send Lovelace card config over WebSocket configuration."""
    return await hass.async_add_executor_job(
        get_card, hass.config.path(LOVELACE_CONFIG_FILE), msg['card_id'],
        msg.get('format', FORMAT_YAML))


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_update_card(hass, connection, msg):
    """Receive Lovelace card configuration over WebSocket and save."""
    return await hass.async_add_executor_job(
        update_card, hass.config.path(LOVELACE_CONFIG_FILE),
        msg['card_id'], msg['card_config'], msg.get('format', FORMAT_YAML))


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_add_card(hass, connection, msg):
    """Add new card to view over WebSocket and save."""
    return await hass.async_add_executor_job(
        add_card, hass.config.path(LOVELACE_CONFIG_FILE),
        msg['view_id'], msg['card_config'], msg.get('position'),
        msg.get('format', FORMAT_YAML))


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_move_card(hass, connection, msg):
    """Move card to different position over WebSocket and save."""
    if 'new_view_id' in msg:
        return await hass.async_add_executor_job(
            move_card_view, hass.config.path(LOVELACE_CONFIG_FILE),
            msg['card_id'], msg['new_view_id'], msg.get('new_position'))

    return await hass.async_add_executor_job(
        move_card, hass.config.path(LOVELACE_CONFIG_FILE),
        msg['card_id'], msg.get('new_position'))


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_delete_card(hass, connection, msg):
    """Delete card from Lovelace over WebSocket and save."""
    return await hass.async_add_executor_job(
        delete_card, hass.config.path(LOVELACE_CONFIG_FILE), msg['card_id'])


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_get_view(hass, connection, msg):
    """Send Lovelace view config over WebSocket config."""
    return await hass.async_add_executor_job(
        get_view, hass.config.path(LOVELACE_CONFIG_FILE), msg['view_id'],
        msg.get('format', FORMAT_YAML))


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_update_view(hass, connection, msg):
    """Receive Lovelace card config over WebSocket and save."""
    return await hass.async_add_executor_job(
        update_view, hass.config.path(LOVELACE_CONFIG_FILE),
        msg['view_id'], msg['view_config'], msg.get('format', FORMAT_YAML))


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_add_view(hass, connection, msg):
    """Add new view over WebSocket and save."""
    return await hass.async_add_executor_job(
        add_view, hass.config.path(LOVELACE_CONFIG_FILE),
        msg['view_config'], msg.get('position'),
        msg.get('format', FORMAT_YAML))


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_move_view(hass, connection, msg):
    """Move view to different position over WebSocket and save."""
    return await hass.async_add_executor_job(
        move_view, hass.config.path(LOVELACE_CONFIG_FILE),
        msg['view_id'], msg['new_position'])


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_delete_view(hass, connection, msg):
    """Delete card from Lovelace over WebSocket and save."""
    return await hass.async_add_executor_job(
        delete_view, hass.config.path(LOVELACE_CONFIG_FILE), msg['view_id'])
