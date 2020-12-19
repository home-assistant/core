"""Config flow for the Pioneer platform."""
import logging

import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TIMEOUT
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_SOURCES,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    POSSIBLE_SOURCES,
)

_LOGGER = logging.getLogger(__name__)


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    def __init__(self):
        """Initialize Pioneer config flow."""
        self._host = None
        self._name = DEFAULT_NAME
        self._port = DEFAULT_PORT
        self._timeout = DEFAULT_TIMEOUT
        self._selected_sources = {}
        self._renamed_sources = {}

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    @property
    def connection_parameters_schema(self):
        """Return schema for the receiver's connection parameters."""
        return vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
            }
        )

    @property
    def select_sources_schema(self):
        """Return schema for possible sources to be available for the media player."""
        return vol.Schema(
            {
                vol.Optional(source_name, default=properties["common"]): cv.boolean
                for source_name, properties in sorted(
                    POSSIBLE_SOURCES.items(), key=self.__tuple_key_casefold()
                )
            }
        )

    @property
    def rename_sources_schema(self):
        """Return schema based on the user previously selected sources."""
        return vol.Schema(
            {
                vol.Optional(source_name): cv.string
                for source_name in sorted(
                    self._selected_sources.keys(), key=self.__tuple_key_casefold()
                )
            }
        )

    async def async_step_user(self, user_input=None):
        """User initiated config flow."""
        if user_input is None:
            return self.async_show_form(step_id="user")

        return self.async_show_form(
            step_id="connection_details", data_schema=self.connection_parameters_schema
        )

    async def async_step_connection_details(self, user_input=None):
        """In this step the user must enter the host and port of the receiver."""

        if user_input is None:
            return self.async_show_form(
                step_id="connection_details",
                data_schema=self.connection_parameters_schema,
            )
        elif user_input[CONF_HOST] is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            self._host = user_input[CONF_HOST]
            self._name = user_input[CONF_NAME]
            self._port = user_input[CONF_PORT]
            self._timeout = user_input[CONF_TIMEOUT]

            return self.async_show_form(
                step_id="select_sources", data_schema=self.select_sources_schema
            )

    async def async_step_select_sources(self, user_input=None):
        """In this step the user can select which sources will be shown (they differ from receiver to receiver)."""

        if user_input is None:
            return self.async_show_form(
                step_id="select_sources", data_schema=self.select_sources_schema
            )

        self._selected_sources = {
            source_name: POSSIBLE_SOURCES[source_name]["code"]
            for source_name, v in user_input.items()
            if v is True
        }

        _LOGGER.debug(self._selected_sources)

        return self.async_show_form(
            step_id="rename_sources", data_schema=self.rename_sources_schema
        )

    async def async_step_rename_sources(self, user_input=None):
        """In this step the user can rename sources (e.g., HDMI1 to Kodi) keeping the underlying protocol's code."""

        if user_input is None:
            return self.async_show_form(
                step_id="rename_sources", data_schema=self.rename_sources_schema
            )

        self._renamed_sources = {
            user_input.get(source_name, source_name): value
            for source_name, value in self._selected_sources.items()
        }

        _LOGGER.debug(self._renamed_sources)

        return self.async_create_entry(
            title=self._name,
            data={
                CONF_NAME: self._name,
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_TIMEOUT: self._timeout,
                CONF_SOURCES: self._renamed_sources,
            },
        )

    @staticmethod
    def __tuple_key_casefold():
        return lambda x: x[0].casefold()
