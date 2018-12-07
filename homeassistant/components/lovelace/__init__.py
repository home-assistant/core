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

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
CONF_LEGACY = 'legacy'

LOVELACE_CONFIG_FILE = 'ui-lovelace.yaml'

SCHEMA_GET_LOVELACE_UI = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'):
        vol.Any(WS_TYPE_GET_LOVELACE_UI, OLD_WS_TYPE_GET_LOVELACE_UI),
})

SCHEMA_SAVE_CONFIG = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_SAVE_CONFIG,
    vol.Required('config'): vol.Any(str, dict),
})


class LegacyError(HomeAssistantError):
    """Legacy Error."""


class LovelaceStorage:
    """Class to handle Storage based Lovelace config."""

    def __init__(self, hass):
        """Initialize Lovelace config based on storage helper."""
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self._config = None

    async def async_load(self):
        """Load config."""
        if self._config is None:
            self._config = await self._store.async_load()

        return self._config

    async def async_save(self, config):
        """Save config."""
        self._config = config
        await self._store.async_save(config)


class LovelaceYAML:
    """Class to handle YAML-based Lovelace config."""

    def __init__(self, hass):
        """Initialize the YAML config."""
        self.hass = hass

    async def async_load(self):
        """Load config."""
        return await hass.async_add_executor_job(load_config, hass,
                                                 msg.get('force', False))

    async def async_save(self, config):
        """Save config."""
        raise NotImplementedError


async def async_setup(hass, config):
    """Set up the Lovelace commands."""
    if config.get(DOMAIN, {}).get(CONF_LEGACY):
        hass.data[DOMAIN] = LovelaceYAML(hass)
    else:
        hass.data[DOMAIN] = LovelaceStorage(hass)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_GET_LOVELACE_UI, websocket_lovelace_config,
        SCHEMA_GET_LOVELACE_UI)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_SAVE_CONFIG, websocket_lovelace_save_config,
        SCHEMA_SAVE_CONFIG)

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
        except LegacyError:
            error = 'legacy_mode', 'Not allowed in legacy mode.'
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
    return await hass.data[DOMAIN].async_load()


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_save_config(hass, connection, msg):
    """Save Lovelace UI configuration."""
    await hass.data[DOMAIN].async_save(msg['config'])
