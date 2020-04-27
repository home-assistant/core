"""Config flow to configure forked-daapd devices."""

import logging

from pyforked_daapd import ForkedDaapdAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (  # pylint:disable=unused-import
    CONF_PIPE_CONTROL,
    CONF_PIPE_CONTROL_PORT,
    CONF_TTS_PAUSE_TIME,
    CONF_TTS_VOLUME,
    CONFIG_FLOW_UNIQUE_ID,
    DEFAULT_PIPE_CONTROL_PORT,
    DEFAULT_PORT,
    DEFAULT_TTS_PAUSE_TIME,
    DEFAULT_TTS_VOLUME,
    DOMAIN,
    FD_NAME,
)

_LOGGER = logging.getLogger(__name__)


# Can't use all vol types: https://github.com/home-assistant/core/issues/32819
DATA_SCHEMA_DICT = {
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Optional(CONF_PASSWORD, default=""): str,
}

ERROR_LOOKUP_DICT = {
    "websocket_not_enabled": "websocket_not_enabled",
    "wrong_host_or_port": "wrong_host_or_port",
    "wrong_password": "wrong_password",
    "wrong_server_type": "wrong_server_type",
}


class ForkedDaapdOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a forked-daapd options flow."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="options", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_TTS_PAUSE_TIME,
                        default=self.config_entry.options.get(
                            CONF_TTS_PAUSE_TIME, DEFAULT_TTS_PAUSE_TIME
                        ),
                    ): float,
                    vol.Optional(
                        CONF_TTS_VOLUME,
                        default=self.config_entry.options.get(
                            CONF_TTS_VOLUME, DEFAULT_TTS_VOLUME
                        ),
                    ): float,
                    vol.Optional(
                        CONF_PIPE_CONTROL,
                        default=self.config_entry.options.get(CONF_PIPE_CONTROL),
                    ): str,  # https://github.com/home-assistant/core/issues/32819
                    vol.Optional(
                        CONF_PIPE_CONTROL_PORT,
                        default=self.config_entry.options.get(
                            CONF_PIPE_CONTROL_PORT, DEFAULT_PIPE_CONTROL_PORT
                        ),
                    ): int,
                }
            ),
        )


def fill_in_schema_dict(some_input):
    """Fill in schema dict defaults from user_input."""
    schema_dict = {}
    for field, _type in DATA_SCHEMA_DICT.items():
        if some_input.get(str(field)):
            schema_dict[
                vol.Optional(str(field), default=some_input[str(field)])
            ] = _type
        else:
            schema_dict[field] = _type
    return schema_dict


class ForkedDaapdFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a forked-daapd config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize."""
        self.discovery_schema = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return options flow handler."""
        return ForkedDaapdOptionsFlowHandler(config_entry)

    async def validate_input(self, user_input):
        """Validate the user input."""
        websession = async_get_clientsession(self.hass)
        return await ForkedDaapdAPI.test_connection(
            websession=websession,
            host=user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            password=user_input[CONF_PASSWORD],
        )

    async def async_step_user(self, user_input=None):
        """Handle a forked-daapd config flow start.

        Manage device specific parameters.
        """
        if user_input is not None:
            validate_result = await self.validate_input(user_input)
            if validate_result == "ok":  # success
                _LOGGER.debug("Connected successfully. Creating entry")
                return self.async_create_entry(
                    title=f"{FD_NAME} server", data=user_input
                )
            validate_result = ERROR_LOOKUP_DICT.get(validate_result, "unknown_error")
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(fill_in_schema_dict(user_input)),
                errors={"base": validate_result},
            )
        if self.discovery_schema:  # stop at form to allow user to set up manually
            return self.async_show_form(
                step_id="user", data_schema=self.discovery_schema, errors={}
            )
        await self.async_set_unique_id(CONFIG_FLOW_UNIQUE_ID)  # only allow one entry
        self._abort_if_unique_id_configured()
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(DATA_SCHEMA_DICT), errors={}
        )

    async def async_step_zeroconf(self, discovery_info):
        """Prepare configuration for a discovered forked-daapd device."""
        await self.async_set_unique_id(CONFIG_FLOW_UNIQUE_ID)  # only allow one entry
        self._abort_if_unique_id_configured()
        if not (
            discovery_info.get("properties")
            and discovery_info["properties"].get("mtd-version")
        ):
            return self.async_abort(reason="not_forked_daapd")
        zeroconf_data = {
            CONF_HOST: discovery_info["host"],
            CONF_PORT: int(discovery_info["port"]),
            CONF_NAME: discovery_info["properties"]["Machine Name"],
        }
        self.discovery_schema = vol.Schema(fill_in_schema_dict(zeroconf_data))
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context.update({"title_placeholders": zeroconf_data})
        return await self.async_step_user()
