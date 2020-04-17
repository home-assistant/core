"""Config flow to configure forked-daapd devices."""

import asyncio
import concurrent
import logging

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (  # pylint:disable=unused-import
    CONF_DEFAULT_VOLUME,
    CONF_PIPE_CONTROL,
    CONF_PIPE_CONTROL_PORT,
    CONF_TTS_PAUSE_TIME,
    CONF_TTS_VOLUME,
    DEFAULT_NAME,
    DEFAULT_PIPE_CONTROL_PORT,
    DEFAULT_PORT,
    DEFAULT_TTS_PAUSE_TIME,
    DEFAULT_TTS_VOLUME,
    DEFAULT_VOLUME,
    DOMAIN,
    FD_NAME,
    SERVER_UNIQUE_ID,
)

_LOGGER = logging.getLogger(__name__)


# Can't use all vol types: https://github.com/home-assistant/core/issues/32819
DATA_SCHEMA_DICT = {
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Optional(CONF_PASSWORD, default=""): str,
    vol.Optional(CONF_DEFAULT_VOLUME, default=DEFAULT_VOLUME): float,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
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
                    ): float,  # vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
                    vol.Optional(
                        CONF_TTS_VOLUME,
                        default=self.config_entry.options.get(
                            CONF_TTS_VOLUME, DEFAULT_TTS_VOLUME
                        ),
                    ): float,
                    vol.Optional(
                        CONF_PIPE_CONTROL,
                        default=self.config_entry.options.get(CONF_PIPE_CONTROL),
                    ): str,  # https://github.com/home-assistant/core/issues/32819 #vol.In(["", "librespot-java"]),
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
        self.discovery_schema = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return options flow handler."""
        return ForkedDaapdOptionsFlowHandler(config_entry)

    async def validate_input(self, user_input):
        """Validate the user input."""
        try:
            websession = async_get_clientsession(self.hass)
            url = f"http://{user_input[CONF_HOST]}:{user_input[CONF_PORT]}/api/config"
            auth = (
                aiohttp.BasicAuth(login="admin", password=user_input[CONF_PASSWORD])
                if user_input.get(CONF_PASSWORD)
                else None
            )
            _LOGGER.debug("Trying to connect to %s with auth %s", url, auth)
            async with websession.get(
                url=url, auth=auth, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                json = await resp.json()
                _LOGGER.debug("JSON %s", json)
                if json["websocket_port"] == 0:
                    return "websocket_not_enabled"
                return "ok"
        except (
            aiohttp.ClientConnectionError,
            asyncio.TimeoutError,
            # pylint: disable=protected-access
            concurrent.futures._base.TimeoutError,  # maybe related to https://github.com/aio-libs/aiohttp/issues/1207
            aiohttp.InvalidURL,
        ):
            return "wrong_host_or_port"
        except aiohttp.ClientResponseError:
            return "wrong_password_or_server_type"
        finally:
            pass
        return "unknown_error"

    async def async_step_user(self, user_input=None):
        """Handle a forked-daapd config flow start.

        Manage device specific parameters.
        """
        await self.async_set_unique_id(SERVER_UNIQUE_ID)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            validate_result = await self.validate_input(user_input)
            if validate_result == "ok":  # success
                _LOGGER.debug("Connected successfully. Creating entry.")
                return self.async_create_entry(
                    title=f"{FD_NAME} server", data=user_input
                )

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(fill_in_schema_dict(user_input)),
                errors={"base": validate_result},
            )
        if self.discovery_schema:
            return self.async_show_form(
                step_id="user", data_schema=self.discovery_schema, errors={}
            )
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(DATA_SCHEMA_DICT), errors={}
        )

    async def async_step_zeroconf(self, discovery_info):
        """Prepare configuration for a discovered forked-daapd device."""
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
        return await self.async_step_user()
