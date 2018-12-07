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
import homeassistant.util.ruamel_yaml as yaml

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'lovelace'
DATA_LOVELACE_YAML = 'lovelace_yaml'
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
CONF_LEGACY = 'legacy'

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
        self._data = {'config': config}
        await self._store.async_save(config)


class LovelaceYAML:
    """Class to handle YAML-based Lovelace config."""

    def __init__(self, hass):
        """Initialize the YAML config."""
        self.hass = hass

    async def async_load(self, force):
        """Load config."""
        return await self.hass.async_add_executor_job(self._load_config, force)

    def _load_config(self, force):
        """Load the actual config."""
        fname = self.hass.config.path(LOVELACE_CONFIG_FILE)
        # Check for a cached version of the config
        if not force and DATA_LOVELACE_YAML in self.hass.data:
            config, last_update = self.hass.data[DATA_LOVELACE_YAML]
            modtime = os.path.getmtime(fname)
            if config and last_update > modtime:
                return config

        try:
            config = yaml.load_yaml(fname, False)
        except FileNotFoundError:
            raise ConfigNotFound from None

        self.hass.data[DATA_LOVELACE_YAML] = (config, time.time())
        return config

    async def async_save(self, config):
        """Save config."""
        raise HomeAssistantError('Not supported')


async def async_setup(hass, config):
    """Set up the Lovelace commands."""
    legacy = config.get(DOMAIN, {}).get(CONF_LEGACY)

    await hass.components.frontend.async_register_built_in_panel(DOMAIN, {
        'legacy': legacy
    })

    hass.data[DOMAIN] = LovelaceYAML(hass) if legacy else LovelaceStorage(hass)

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
        except ConfigNotFound:
            error = 'config_not_found', 'No config found.'
        except yaml.UnsupportedYamlError as err:
            error = 'unsupported_error', str(err)
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
