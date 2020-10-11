"""Config flow for 1-Wire component."""
import logging
import os

from pyownet import protocol
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE

from .const import (  # pylint: disable=unused-import
    CONF_MOUNT_DIR,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DEFAULT_OWSERVER_HOST,
    DEFAULT_OWSERVER_PORT,
    DEFAULT_SYSBUS_MOUNT_DIR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class OneWireFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle 1-Wire config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

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

        proxy_types = [CONF_TYPE_OWSERVER, CONF_TYPE_SYSBUS]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_TYPE): vol.In(proxy_types)}),
            errors=errors,
        )

    async def async_step_owserver(self, user_input=None):
        """Handle OWServer configuration."""
        errors = {}
        if user_input:
            self.onewire_config.update(user_input)
            owhost = user_input.get(CONF_HOST)
            owport = user_input.get(CONF_PORT)
            try:
                await self.hass.async_add_executor_job(protocol.proxy, owhost, owport)
                await self.async_set_unique_id(
                    f"{CONF_TYPE_OWSERVER}:{owhost}:{owport}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=owhost, data=self.onewire_config)
            except (protocol.Error, protocol.ConnError) as exc:
                _LOGGER.error(
                    "Cannot connect to owserver on %s:%d, got: %s", owhost, owport, exc
                )
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="owserver",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_OWSERVER_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_OWSERVER_PORT): int,
                }
            ),
            errors=errors,
        )

    async def async_step_mount_dir(self, user_input=None):
        """Handle OWFS / SysBus configuration."""
        errors = {}
        if user_input:
            self.onewire_config.update(user_input)
            mount_dir = user_input.get(CONF_MOUNT_DIR)
            if os.path.isdir(mount_dir):
                await self.async_set_unique_id(f"{CONF_TYPE_SYSBUS}:{mount_dir}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=mount_dir, data=self.onewire_config
                )
            errors["base"] = "invalid_path"

        return self.async_show_form(
            step_id="mount_dir",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MOUNT_DIR, default=DEFAULT_SYSBUS_MOUNT_DIR): str,
                }
            ),
            errors=errors,
        )
