"""Config flow to configure OneWire component."""
import os

from pyownet import protocol
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import callback

from .const import (
    CONF_MOUNT_DIR,
    DEFAULT_MOUNT_DIR,
    DEFAULT_OWFS_MOUNT_DIR,
    DEFAULT_PORT,
    DOMAIN,
    LOGGER,
)

CONF_TYPE_OWSERVER = "OWServer"
CONF_TYPE_OWFS = "OWFS"
CONF_TYPE_SYSBUS = "SysBus"


@callback
def get_master_gateway(hass):
    """Return the gateway which is marked as master."""
    for gateway in hass.data[DOMAIN].values():
        if gateway.master:
            return gateway


class OneWireFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a OneWire config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    _hassio_discovery = None

    async def async_step_user(self, user_input=None):
        """Handle a OneWire config flow start.

        Let user manually input configuration.
        """
        errors = {}
        if user_input is not None:

            if CONF_TYPE_OWSERVER == user_input[CONF_TYPE]:
                return await self.async_step_owserver()
            if CONF_TYPE_OWFS == user_input[CONF_TYPE]:
                return await self.async_step_owfs()
            if CONF_TYPE_SYSBUS == user_input[CONF_TYPE]:
                if os.path.isdir(DEFAULT_MOUNT_DIR):
                    user_input[CONF_MOUNT_DIR] = DEFAULT_MOUNT_DIR
                    return self.async_create_entry(
                        title=DEFAULT_MOUNT_DIR, data=user_input
                    )
                errors["base"] = "invalid_path"

        proxy_types = [CONF_TYPE_OWSERVER, CONF_TYPE_OWFS, CONF_TYPE_SYSBUS]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_TYPE): vol.In(proxy_types)}),
            errors=errors,
        )

    async def async_step_owserver(self, user_input=None):
        """Handle OWServer configuration."""
        errors = {}
        if user_input:
            owhost = user_input.get(CONF_HOST)
            owport = user_input.get(CONF_PORT)
            try:
                owproxy = protocol.proxy(host=owhost, port=owport)
                owproxy.dir()
                return self.async_create_entry(title=owhost, data=user_input)
            except (protocol.Error, protocol.ConnError) as exc:
                LOGGER.error(
                    "Cannot connect to owserver on %s:%d, got: %s", owhost, owport, exc
                )
                errors["base"] = "connection_error"

        return self.async_show_form(
            step_id="owserver",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
        )

    async def async_step_owfs(self, user_input=None):
        """Handle OWServer configuration."""
        errors = {}
        if user_input:
            owpath = user_input.get(CONF_MOUNT_DIR)
            if os.path.isdir(owpath):
                return self.async_create_entry(title=owpath, data=user_input)
            errors["base"] = "invalid_path"

        return self.async_show_form(
            step_id="owfs",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MOUNT_DIR, default=DEFAULT_OWFS_MOUNT_DIR): str,
                }
            ),
            errors=errors,
        )
