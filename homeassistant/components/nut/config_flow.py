"""Config flow for Network UPS Tools (NUT) integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_ALIAS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_USERNAME,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import PyNUTData, find_resources_in_config_entry, pynutdata_status
from .const import DEFAULT_HOST, DEFAULT_NAME, DEFAULT_PORT, SENSOR_TYPES
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


SENSOR_DICT = {sensor_id: SENSOR_TYPES[sensor_id][0] for sensor_id in SENSOR_TYPES}

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_RESOURCES): cv.multi_select(SENSOR_DICT),
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_ALIAS): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    host = data[CONF_HOST]
    port = data[CONF_PORT]
    alias = data.get(CONF_ALIAS)
    username = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)

    data = PyNUTData(host, port, alias, username, password)

    status = await hass.async_add_executor_job(pynutdata_status, data)

    if not status:
        raise CannotConnect

    return {"title": _format_host_port_alias(host, port, alias)}


def _format_host_port_alias(host, port, alias):
    """Format a host, port, and alias so it can be used for comparison or display."""
    if alias:
        return f"{alias}@{host}:{port}"
    return f"{host}:{port}"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Network UPS Tools (NUT)."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if self._host_port_alias_already_configured(
                user_input[CONF_HOST], user_input[CONF_PORT], user_input.get(CONF_ALIAS)
            ):
                return self.async_abort(reason="already_configured")
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    def _host_port_alias_already_configured(self, host, port, alias):
        """See if we already have a nut entry matching user input configured."""
        existing_host_port_aliases = {
            _format_host_port_alias(
                entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data.get(CONF_ALIAS)
            )
            for entry in self._async_current_entries()
        }
        return _format_host_port_alias(host, port, alias) in existing_host_port_aliases

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for nut."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        resources = find_resources_in_config_entry(self.config_entry)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_RESOURCES, default=resources): cv.multi_select(
                    SENSOR_DICT
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
