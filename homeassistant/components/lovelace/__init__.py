"""
Support for the Lovelace UI.

For more details about this component, please refer to the documentation
at https://www.home-assistant.io/lovelace/
"""
from functools import wraps
import logging
import os
import time

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.yaml import load_yaml

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'lovelace'
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
CONF_MODE = 'mode'
MODE_YAML = 'yaml'
MODE_STORAGE = 'storage'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_MODE, default=MODE_STORAGE):
        vol.All(vol.Lower, vol.In([MODE_YAML, MODE_STORAGE])),
    }),
}, extra=vol.ALLOW_EXTRA)


LOVELACE_CONFIG_FILE = 'ui-lovelace.yaml'

WS_TYPE_GET_LOVELACE_UI = 'lovelace/config'
WS_TYPE_SAVE_CONFIG = 'lovelace/config/save'

SCHEMA_GET_LOVELACE_UI = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_GET_LOVELACE_UI,
    vol.Optional('force', default=False): bool,
})

SCHEMA_SAVE_CONFIG = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_SAVE_CONFIG,
    vol.Required('config'): vol.Any(str, dict),
})


class ConfigNotFound(HomeAssistantError):
    """When no config available."""


async def async_setup(hass, config):
    """Set up the Lovelace commands."""
    # Pass in default to `get` because defaults not set if loaded as dep
    mode = config.get(DOMAIN, {}).get(CONF_MODE, MODE_STORAGE)

    await hass.components.frontend.async_register_built_in_panel(
        DOMAIN, config={
            'mode': mode
        })

    if mode == MODE_YAML:
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


class LovelaceStorage:
    """Class to handle Storage based Lovelace config."""

    def __init__(self, hass):
        """Initialize Lovelace config based on storage helper."""
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self._data = None

    async def async_load(self, force):
        """Load config."""
        if self._data is None:
            data = await self._store.async_load()
            self._data = data if data else {'config': None}

        config = self._data['config']

        if config is None:
            raise ConfigNotFound

        return config

    async def async_save(self, config):
        """Save config."""
        self._data['config'] = config
        await self._store.async_save(self._data)


class LovelaceYAML:
    """Class to handle YAML-based Lovelace config."""

    def __init__(self, hass):
        """Initialize the YAML config."""
        self.hass = hass
        self._cache = None

    async def async_load(self, force):
        """Load config."""
        return await self.hass.async_add_executor_job(self._load_config, force)

    def _load_config(self, force):
        """Load the actual config."""
        fname = self.hass.config.path(LOVELACE_CONFIG_FILE)
        # Check for a cached version of the config
        if not force and self._cache is not None:
            config, last_update = self._cache
            modtime = os.path.getmtime(fname)
            if config and last_update > modtime:
                return config

        try:
            config = load_yaml(fname)
        except FileNotFoundError:
            raise ConfigNotFound from None

        self._cache = (config, time.time())
        return config

    async def async_save(self, config):
        """Save config."""
        raise HomeAssistantError('Not supported')


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
        except ConfigNotFound:
            error = 'config_not_found', 'No config found.'
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
    return await hass.data[DOMAIN].async_load(msg['force'])


@websocket_api.async_response
@handle_yaml_errors
async def websocket_lovelace_save_config(hass, connection, msg):
    """Save Lovelace UI configuration."""
    await hass.data[DOMAIN].async_save(msg['config'])
