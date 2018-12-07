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
        return await self.hass.async_add_executor_job(self._load_config)

    def _load_config(self):
        """Load the actual config."""
        fname = self.hass.config.path(LOVELACE_CONFIG_FILE)
        # Check for a cached version of the config
        if DATA_LOVELACE_YAML in self.hass.data:
            config, last_update = self.hass.data[DATA_LOVELACE_YAML]
            modtime = os.path.getmtime(fname)
            if config and last_update > modtime:
                return config

        config = yaml.load_yaml(fname, False)
        self.hass.data[DATA_LOVELACE_YAML] = (config, time.time())
        return config

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
        except LegacyError:
            error = 'legacy_mode', 'Not allowed in legacy mode.'
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
