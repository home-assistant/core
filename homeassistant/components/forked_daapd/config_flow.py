"""Config flow to configure forked-daapd devices."""

from contextlib import suppress
import logging
from typing import Any

from pyforked_daapd import ForkedDaapdAPI
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_LIBRESPOT_JAVA_PORT,
    CONF_MAX_PLAYLISTS,
    CONF_TTS_PAUSE_TIME,
    CONF_TTS_VOLUME,
    DEFAULT_PORT,
    DEFAULT_TTS_PAUSE_TIME,
    DEFAULT_TTS_VOLUME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


# Can't use all vol types: https://github.com/home-assistant/core/issues/32819
DATA_SCHEMA_DICT = {
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Optional(CONF_PASSWORD, default=""): str,
}

TEST_CONNECTION_ERROR_DICT = {
    "forbidden": "forbidden",
    "ok": "ok",
    "websocket_not_enabled": "websocket_not_enabled",
    "wrong_host_or_port": "wrong_host_or_port",
    "wrong_password": "wrong_password",
    "wrong_server_type": "wrong_server_type",
}


class ForkedDaapdOptionsFlowHandler(OptionsFlow):
    """Handle a forked-daapd options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
                        CONF_LIBRESPOT_JAVA_PORT,
                        default=self.config_entry.options.get(
                            CONF_LIBRESPOT_JAVA_PORT, 24879
                        ),
                    ): int,
                    vol.Optional(
                        CONF_MAX_PLAYLISTS,
                        default=self.config_entry.options.get(CONF_MAX_PLAYLISTS, 10),
                    ): int,
                }
            ),
        )


def fill_in_schema_dict(some_input):
    """Fill in schema dict defaults from user_input."""
    schema_dict = {}
    for field, _type in DATA_SCHEMA_DICT.items():
        if some_input.get(str(field)):
            schema_dict[vol.Optional(str(field), default=some_input[str(field)])] = (
                _type
            )
        else:
            schema_dict[field] = _type
    return schema_dict


class ForkedDaapdFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a forked-daapd config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.discovery_schema: vol.Schema | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ForkedDaapdOptionsFlowHandler:
        """Return options flow handler."""
        return ForkedDaapdOptionsFlowHandler(config_entry)

    async def validate_input(self, user_input):
        """Validate the user input."""
        websession = async_get_clientsession(self.hass)
        validate_result = await ForkedDaapdAPI.test_connection(
            websession=websession,
            host=user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            password=user_input[CONF_PASSWORD],
        )
        validate_result[0] = TEST_CONNECTION_ERROR_DICT.get(
            validate_result[0], "unknown_error"
        )
        return validate_result

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a forked-daapd config flow start.

        Manage device specific parameters.
        """
        if user_input is not None:
            # check for any entries with same host, abort if found
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            validate_result = await self.validate_input(user_input)
            if validate_result[0] == "ok":  # success
                _LOGGER.debug("Connected successfully. Creating entry")
                return self.async_create_entry(
                    title=validate_result[1], data=user_input
                )
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(fill_in_schema_dict(user_input)),
                errors={"base": validate_result[0]},
            )
        if self.discovery_schema:  # stop at form to allow user to set up manually
            return self.async_show_form(
                step_id="user", data_schema=self.discovery_schema, errors={}
            )
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(DATA_SCHEMA_DICT), errors={}
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a discovered forked-daapd device."""
        version_num = 0
        zeroconf_properties = discovery_info.properties
        if zeroconf_properties.get("Machine Name"):
            with suppress(ValueError):
                version_num = int(
                    zeroconf_properties.get("mtd-version", "0").split(".")[0]
                )
        if version_num < 27:
            return self.async_abort(reason="not_forked_daapd")
        await self.async_set_unique_id(zeroconf_properties["Machine Name"])
        self._abort_if_unique_id_configured()

        # Update title and abort if we already have an entry for this host
        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST) != discovery_info.host:
                continue
            self.hass.config_entries.async_update_entry(
                entry,
                title=zeroconf_properties["Machine Name"],
            )
            return self.async_abort(reason="already_configured")

        zeroconf_data = {
            CONF_HOST: discovery_info.host,
            CONF_PORT: discovery_info.port,
            CONF_NAME: zeroconf_properties["Machine Name"],
        }
        self.discovery_schema = vol.Schema(fill_in_schema_dict(zeroconf_data))
        self.context.update({"title_placeholders": zeroconf_data})
        return await self.async_step_user()
