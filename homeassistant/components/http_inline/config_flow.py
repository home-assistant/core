"""Config flow to configure the WebController-Relay integration."""

import logging

import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, HTTP_OK

from .const import (  # pylint: disable=unused-import
    CONF_NB_RELAYS,
    CONF_PATH_PATTERN_READ,
    CONF_PATH_PATTERN_WRITE,
    CONF_RELAY_I_NAME_PATTERN,
    CONF_RELAY_NAMES,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_NB_RELAYS,
    DEFAULT_PATH_PATTERN_READ,
    DEFAULT_PATH_PATTERN_WRITE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class HttpInlineFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize HTTP_inline config flow."""
        self._host = None
        self._name = None
        self._path_read = None
        self._path_write = None
        self._nb_relays = 0
        self._relay_names = []

    def _global_data_schema(self, user_input=None):
        if user_input is None:
            user_input = {}

        return vol.Schema(
            {
                vol.Required(
                    CONF_HOST, default=user_input.get(CONF_HOST, DEFAULT_HOST)
                ): str,
                vol.Required(
                    CONF_NB_RELAYS,
                    default=user_input.get(CONF_NB_RELAYS, DEFAULT_NB_RELAYS),
                ): int,
                vol.Optional(
                    CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                ): str,
                vol.Optional(
                    CONF_PATH_PATTERN_READ,
                    default=user_input.get(
                        CONF_PATH_PATTERN_READ, DEFAULT_PATH_PATTERN_READ
                    ),
                ): str,
                vol.Optional(
                    CONF_PATH_PATTERN_WRITE,
                    default=user_input.get(
                        CONF_PATH_PATTERN_WRITE, DEFAULT_PATH_PATTERN_WRITE
                    ),
                ): str,
            }
        )

    def _relays_data_schema(self, user_input=None):
        if user_input is None:
            user_input = {}

        schema = vol.Schema({})
        for i in range(0, self._nb_relays):
            name = CONF_RELAY_I_NAME_PATTERN.format(i)
            default = f"{self._name} #{i}"

            schema = schema.extend({vol.Optional(name, default=default): str})

        return schema

    def _export(self):
        return {
            CONF_HOST: self._host,
            CONF_NAME: self._name,
            CONF_PATH_PATTERN_READ: self._path_read,
            CONF_PATH_PATTERN_WRITE: self._path_write,
            CONF_NB_RELAYS: self._nb_relays,
            CONF_RELAY_NAMES: self._relay_names,
        }

    def _show_global_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""

        return self.async_show_form(
            step_id="user",
            data_schema=self._global_data_schema(user_input),
            errors=errors or {},
        )

    def _show_relays_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user_bis."""
        return self.async_show_form(
            step_id="relay",
            data_schema=self._relays_data_schema(user_input),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return self._show_global_setup_form(user_input, errors)

        await self.async_set_unique_id(user_input[CONF_HOST])

        return await self.async_step_link(user_input)

    async def async_step_link(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        try:
            request = requests.get(user_input[CONF_HOST], timeout=10)
            if request.status_code == HTTP_OK:
                self._host = user_input[CONF_HOST]
                self._name = user_input.get(CONF_NAME, user_input[CONF_HOST])
                self._path_read = user_input.get(
                    CONF_PATH_PATTERN_READ, DEFAULT_PATH_PATTERN_READ
                )
                self._path_write = user_input.get(
                    CONF_PATH_PATTERN_WRITE, DEFAULT_PATH_PATTERN_WRITE
                )
                self._nb_relays = user_input[CONF_NB_RELAYS]

                return await self.async_step_relay()

            _LOGGER.error("Server error %d", request.status_code)
            errors[CONF_HOST] = "Server error"

        except requests.exceptions.MissingSchema:
            _LOGGER.error(
                "Missing host or schema in configuration. Add http:// to your URL"
            )
            errors[
                CONF_HOST
            ] = "Missing host or schema in configuration. Add http:// to your URL"

        except requests.exceptions.ConnectionError:
            _LOGGER.error("No route to device at %s", user_input[CONF_HOST])
            errors[CONF_HOST] = "No route to device"

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error connecting with server at %s", user_input[CONF_HOST]
            )
            errors["base"] = "unknown"

        return self._show_global_setup_form(user_input, errors)

    async def async_step_relay(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return self._show_relays_setup_form(user_input, errors)

        self._relay_names = [None] * self._nb_relays

        for i in range(0, self._nb_relays):
            key = CONF_RELAY_I_NAME_PATTERN.format(i)
            if key in user_input:
                self._relay_names[i] = user_input[key]
            else:
                return self._show_relays_setup_form(user_input, errors)

        return await self.async_step_import(user_input)

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        if user_input is None:
            user_input = {}

        data = self._export()

        self.hass.data[DOMAIN] = data

        return self.async_create_entry(title=data[CONF_NAME], data=data)
