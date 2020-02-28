"""Support for the Lovelace UI."""
from functools import wraps
import logging
import os
import time

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.yaml import load_yaml

_LOGGER = logging.getLogger(__name__)

DOMAIN = "lovelace"
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
CONF_MODE = "mode"
MODE_YAML = "yaml"
MODE_STORAGE = "storage"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_MODE, default=MODE_STORAGE): vol.All(
                    vol.Lower, vol.In([MODE_YAML, MODE_STORAGE])
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

EVENT_LOVELACE_UPDATED = "lovelace_updated"

LOVELACE_CONFIG_FILE = "ui-lovelace.yaml"


class ConfigNotFound(HomeAssistantError):
    """When no config available."""


async def async_setup(hass, config):
    """Set up the Lovelace commands."""
    # Pass in default to `get` because defaults not set if loaded as dep
    mode = config.get(DOMAIN, {}).get(CONF_MODE, MODE_STORAGE)

    hass.components.frontend.async_register_built_in_panel(
        DOMAIN, config={"mode": mode}
    )

    if mode == MODE_YAML:
        hass.data[DOMAIN] = LovelaceYAML(hass)
    else:
        hass.data[DOMAIN] = LovelaceStorage(hass)

    hass.components.websocket_api.async_register_command(websocket_lovelace_config)

    hass.components.websocket_api.async_register_command(websocket_lovelace_save_config)

    hass.components.websocket_api.async_register_command(
        websocket_lovelace_delete_config
    )

    hass.components.system_health.async_register_info(DOMAIN, system_health_info)

    return True


class LovelaceStorage:
    """Class to handle Storage based Lovelace config."""

    def __init__(self, hass):
        """Initialize Lovelace config based on storage helper."""
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self._data = None
        self._hass = hass

    async def async_get_info(self):
        """Return the YAML storage mode."""
        if self._data is None:
            await self._load()

        if self._data["config"] is None:
            return {"mode": "auto-gen"}

        return _config_info("storage", self._data["config"])

    async def async_load(self, force):
        """Load config."""
        if self._hass.config.safe_mode:
            raise ConfigNotFound

        if self._data is None:
            await self._load()

        config = self._data["config"]

        if config is None:
            raise ConfigNotFound

        return config

    async def async_save(self, config):
        """Save config."""
        if self._hass.config.safe_mode:
            raise HomeAssistantError("Deleting not supported in safe mode")

        if self._data is None:
            await self._load()
        self._data["config"] = config
        self._hass.bus.async_fire(EVENT_LOVELACE_UPDATED)
        await self._store.async_save(self._data)

    async def async_delete(self):
        """Delete config."""
        if self._hass.config.safe_mode:
            raise HomeAssistantError("Deleting not supported in safe mode")

        await self.async_save(None)

    async def _load(self):
        """Load the config."""
        data = await self._store.async_load()
        self._data = data if data else {"config": None}


class LovelaceYAML:
    """Class to handle YAML-based Lovelace config."""

    def __init__(self, hass):
        """Initialize the YAML config."""
        self.hass = hass
        self._cache = None

    async def async_get_info(self):
        """Return the YAML storage mode."""
        try:
            config = await self.async_load(False)
        except ConfigNotFound:
            return {
                "mode": "yaml",
                "error": "{} not found".format(
                    self.hass.config.path(LOVELACE_CONFIG_FILE)
                ),
            }

        return _config_info("yaml", config)

    async def async_load(self, force):
        """Load config."""
        is_updated, config = await self.hass.async_add_executor_job(
            self._load_config, force
        )
        if is_updated:
            self.hass.bus.async_fire(EVENT_LOVELACE_UPDATED)
        return config

    def _load_config(self, force):
        """Load the actual config."""
        fname = self.hass.config.path(LOVELACE_CONFIG_FILE)
        # Check for a cached version of the config
        if not force and self._cache is not None:
            config, last_update = self._cache
            modtime = os.path.getmtime(fname)
            if config and last_update > modtime:
                return False, config

        is_updated = self._cache is not None

        try:
            config = load_yaml(fname)
        except FileNotFoundError:
            raise ConfigNotFound from None

        self._cache = (config, time.time())
        return is_updated, config

    async def async_save(self, config):
        """Save config."""
        raise HomeAssistantError("Not supported")

    async def async_delete(self):
        """Delete config."""
        raise HomeAssistantError("Not supported")


def handle_yaml_errors(func):
    """Handle error with WebSocket calls."""

    @wraps(func)
    async def send_with_error_handling(hass, connection, msg):
        error = None
        try:
            result = await func(hass, connection, msg)
        except ConfigNotFound:
            error = "config_not_found", "No config found."
        except HomeAssistantError as err:
            error = "error", str(err)

        if error is not None:
            connection.send_error(msg["id"], *error)
            return

        if msg is not None:
            await connection.send_big_result(msg["id"], result)
        else:
            connection.send_result(msg["id"], result)

    return send_with_error_handling


@websocket_api.async_response
@websocket_api.websocket_command(
    {"type": "lovelace/config", vol.Optional("force", default=False): bool}
)
@handle_yaml_errors
async def websocket_lovelace_config(hass, connection, msg):
    """Send Lovelace UI config over WebSocket configuration."""
    return await hass.data[DOMAIN].async_load(msg["force"])


@websocket_api.async_response
@websocket_api.websocket_command(
    {"type": "lovelace/config/save", "config": vol.Any(str, dict)}
)
@handle_yaml_errors
async def websocket_lovelace_save_config(hass, connection, msg):
    """Save Lovelace UI configuration."""
    await hass.data[DOMAIN].async_save(msg["config"])


@websocket_api.async_response
@websocket_api.websocket_command({"type": "lovelace/config/delete"})
@handle_yaml_errors
async def websocket_lovelace_delete_config(hass, connection, msg):
    """Delete Lovelace UI configuration."""
    await hass.data[DOMAIN].async_delete()


async def system_health_info(hass):
    """Get info for the info page."""
    return await hass.data[DOMAIN].async_get_info()


def _config_info(mode, config):
    """Generate info about the config."""
    return {
        "mode": mode,
        "resources": len(config.get("resources", [])),
        "views": len(config.get("views", [])),
    }
