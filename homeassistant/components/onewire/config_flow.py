"""Config flow for 1-Wire component."""
import logging
import os

from pyownet import protocol
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE

from .const import (  # pylint: disable=unused-import
    CONF_MOUNT_DIR,
    CONF_TYPE_OWFS,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DEFAULT_OWSERVER_HOST,
    DEFAULT_OWSERVER_PORT,
    DEFAULT_SYSBUS_MOUNT_DIR,
    DOMAIN,
)

DATA_SCHEMA_USER = vol.Schema(
    {vol.Required(CONF_TYPE): vol.In([CONF_TYPE_OWSERVER, CONF_TYPE_SYSBUS])}
)
DATA_SCHEMA_OWSERVER = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_OWSERVER_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_OWSERVER_PORT): int,
    }
)
DATA_SCHEMA_MOUNTDIR = vol.Schema(
    {
        vol.Required(CONF_MOUNT_DIR, default=DEFAULT_SYSBUS_MOUNT_DIR): str,
    }
)

_LOGGER = logging.getLogger(__name__)


class OneWireFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle 1-Wire config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize 1-Wire config flow."""
        self.onewire_config = {}

    async def async_step_user(self, user_input=None):
        """Handle 1-Wire config flow start.

        Let user manually input configuration.
        """
        errors = {}
        if user_input is not None:
            self.onewire_config.update(user_input)
            if CONF_TYPE_OWSERVER == user_input[CONF_TYPE]:
                return await self.async_step_owserver()
            if CONF_TYPE_SYSBUS == user_input[CONF_TYPE]:
                return await self.async_step_mount_dir()

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA_USER,
            errors=errors,
        )

    def get_existing_owserver_entry(self, host: str, port: int):
        """Get existing entry with matching host and port."""
        for config_entry in self.hass.config_entries.async_entries(DOMAIN):
            if (
                config_entry.data[CONF_TYPE] == CONF_TYPE_OWSERVER
                and config_entry.data[CONF_HOST] == host
                and config_entry.data[CONF_PORT] == str(port)
            ):
                return config_entry
        return None

    async def async_step_owserver(self, user_input=None):
        """Handle OWServer configuration."""
        errors = {}
        if user_input:
            self.onewire_config.update(user_input)
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            existing_entry = self.get_existing_owserver_entry(host, port)
            if existing_entry is not None:
                return self.async_abort(reason="already_configured")
            try:
                await self.hass.async_add_executor_job(protocol.proxy, host, port)
            except (protocol.Error, protocol.ConnError) as exc:
                _LOGGER.error(
                    "Cannot connect to owserver on %s:%d, got: %s", host, port, exc
                )
                errors["base"] = "cannot_connect"
            if len(errors) == 0:
                return self.async_create_entry(title=host, data=self.onewire_config)

        return self.async_show_form(
            step_id="owserver",
            data_schema=DATA_SCHEMA_OWSERVER,
            errors=errors,
        )

    async def async_step_mount_dir(self, user_input=None):
        """Handle SysBus configuration."""
        errors = {}
        if user_input:
            self.onewire_config.update(user_input)
            mount_dir = user_input[CONF_MOUNT_DIR]
            await self.async_set_unique_id(f"{CONF_TYPE_SYSBUS}:{mount_dir}")
            self._abort_if_unique_id_configured()
            if await self.hass.async_add_executor_job(os.path.isdir, mount_dir):
                return self.async_create_entry(
                    title=mount_dir, data=self.onewire_config
                )
            _LOGGER.error("Cannot find SysBus directory %s", mount_dir)
            errors["base"] = "invalid_path"

        return self.async_show_form(
            step_id="mount_dir",
            data_schema=DATA_SCHEMA_MOUNTDIR,
            errors=errors,
        )

    async def async_step_import(self, platform_config):
        """Handle import configuration from YAML."""
        # OWServer
        if platform_config[CONF_TYPE] == CONF_TYPE_OWSERVER:
            if CONF_PORT not in platform_config:
                platform_config[CONF_PORT] = DEFAULT_OWSERVER_PORT
            return await self.async_step_owserver(platform_config)

        # SysBus
        if platform_config[CONF_TYPE] == CONF_TYPE_SYSBUS:
            if CONF_MOUNT_DIR not in platform_config:
                platform_config[CONF_MOUNT_DIR] = DEFAULT_SYSBUS_MOUNT_DIR
            return await self.async_step_mount_dir(platform_config)

        # OWFS
        if platform_config[CONF_TYPE] == CONF_TYPE_OWFS:  # pragma: no cover
            # This part of the implementation does not conform to policy regarding 3rd-party libraries, and will not longer be updated.
            # https://developers.home-assistant.io/docs/creating_platform_code_review/#5-communication-with-devicesservices
            await self.async_set_unique_id(
                f"{CONF_TYPE_OWFS}:{platform_config[CONF_MOUNT_DIR]}"
            )
            self._abort_if_unique_id_configured(
                updates=platform_config, reload_on_update=True
            )
            return self.async_create_entry(
                title=platform_config[CONF_MOUNT_DIR], data=platform_config
            )
