"""Config flow for Network UPS Tools (NUT) integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_ALIAS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_USERNAME,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import PyNUTData, find_resources_in_config_entry, pynutdata_status
from .const import DEFAULT_HOST, DEFAULT_PORT, SENSOR_TYPES
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


SENSOR_DICT = {sensor_id: SENSOR_TYPES[sensor_id][0] for sensor_id in SENSOR_TYPES}

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


def _resource_schema(available_resources, selected_resources):
    """Resource selection schema."""

    known_available_resources = {
        sensor_id: sensor[0]
        for sensor_id, sensor in SENSOR_TYPES.items()
        if sensor_id in available_resources
    }

    return vol.Schema(
        {
            vol.Required(CONF_RESOURCES, default=selected_resources): cv.multi_select(
                known_available_resources
            )
        }
    )


def _ups_schema(ups_list):
    """UPS selection schema."""
    ups_map = {ups: ups for ups in ups_list}

    return vol.Schema({vol.Required(CONF_ALIAS): vol.In(ups_map)})


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

    ups_list = await hass.async_add_executor_job(data.list_ups)
    if not ups_list:
        raise CannotConnect

    status = await hass.async_add_executor_job(pynutdata_status, data)
    if not status:
        raise CannotConnect

    return {"ups_list": ups_list, "available_resources": status}


def _format_host_port_alias(user_input):
    """Format a host, port, and alias so it can be used for comparison or display."""
    host = user_input[CONF_HOST]
    port = user_input[CONF_PORT]
    alias = user_input.get(CONF_ALIAS)
    if alias:
        return f"{alias}@{host}:{port}"
    return f"{host}:{port}"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Network UPS Tools (NUT)."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the nut config flow."""
        self.nut_config = {}
        self.available_resources = {}
        self.ups_list = None
        self.title = None

    async def async_step_import(self, user_input=None):
        """Handle the import."""
        errors = {}
        if user_input is not None:
            if self._host_port_alias_already_configured(user_input):
                return self.async_abort(reason="already_configured")
            _, errors = await self._async_validate_or_error(user_input)

            if not errors:
                title = _format_host_port_alias(user_input)
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_user(self, user_input=None):
        """Handle the user input."""
        errors = {}
        if user_input is not None:
            info, errors = await self._async_validate_or_error(user_input)

            if not errors:
                self.nut_config.update(user_input)
                if len(info["ups_list"]) > 1:
                    self.ups_list = info["ups_list"]
                    return await self.async_step_ups()

                self.available_resources.update(info["available_resources"])
                return await self.async_step_resources()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_ups(self, user_input=None):
        """Handle the picking the ups."""
        errors = {}

        if user_input is not None:
            self.nut_config.update(user_input)
            if self._host_port_alias_already_configured(self.nut_config):
                return self.async_abort(reason="already_configured")
            info, errors = await self._async_validate_or_error(self.nut_config)
            if not errors:
                self.available_resources.update(info["available_resources"])
                return await self.async_step_resources()

        return self.async_show_form(
            step_id="ups", data_schema=_ups_schema(self.ups_list), errors=errors,
        )

    async def async_step_resources(self, user_input=None):
        """Handle the picking the resources."""
        if user_input is None:
            return self.async_show_form(
                step_id="resources",
                data_schema=_resource_schema(self.available_resources, []),
            )

        self.nut_config.update(user_input)
        title = _format_host_port_alias(self.nut_config)
        return self.async_create_entry(title=title, data=self.nut_config)

    def _host_port_alias_already_configured(self, user_input):
        """See if we already have a nut entry matching user input configured."""
        existing_host_port_aliases = {
            _format_host_port_alias(entry.data)
            for entry in self._async_current_entries()
        }
        return _format_host_port_alias(user_input) in existing_host_port_aliases

    async def _async_validate_or_error(self, config):
        errors = {}
        info = {}
        try:
            info = await validate_input(self.hass, config)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return info, errors

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

        info = await validate_input(self.hass, self.config_entry.data)

        return self.async_show_form(
            step_id="init",
            data_schema=_resource_schema(info["available_resources"], resources),
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
