"""Config flow for pyLoad integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import CookieJar
from pyloadapi.api import PyLoadAPI
from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_HOST, DEFAULT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SSL, default=False): cv.boolean,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_USER_SUGGESTED_VALUES = {
    CONF_HOST: "homeassistant.local",
    CONF_USERNAME: "pyload",
    CONF_PASSWORD: "pyload",
}


async def validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> None:
    """Validate the user input and try to connect to PyLoad."""

    session = async_create_clientsession(
        hass,
        user_input[CONF_VERIFY_SSL],
        cookie_jar=CookieJar(unsafe=True),
    )
    host = user_input[CONF_HOST]
    port = user_input[CONF_PORT]
    protocol = "https" if user_input[CONF_SSL] else "http"
    url = f"{protocol}://{host}:{port}/"
    pyload = PyLoadAPI(
        session,
        api_url=url,
        username=user_input[CONF_USERNAME],
        password=user_input[CONF_PASSWORD],
    )

    await pyload.login()


class PyLoadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pyLoad."""

    VERSION = 1
    # store values from yaml import so we can use them as
    # suggested values when the configuration step is resumed
    yaml_config: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            try:
                await validate_input(self.hass, user_input)
            except (CannotConnect, ParserError):
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                title = user_input.pop(CONF_NAME, None)
                return self.async_create_entry(
                    title=title or DEFAULT_NAME, data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input or self.yaml_config or STEP_USER_SUGGESTED_VALUES,
            ),
            errors=errors,
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import config from yaml."""

        self.yaml_config = {
            CONF_NAME: import_info.get(CONF_NAME),
            CONF_HOST: import_info.get(CONF_HOST, DEFAULT_HOST),
            CONF_PASSWORD: import_info.get(CONF_PASSWORD, ""),
            CONF_PORT: import_info.get(CONF_PORT, DEFAULT_PORT),
            CONF_SSL: import_info.get(CONF_SSL, False),
            CONF_USERNAME: import_info.get(CONF_USERNAME, ""),
            CONF_VERIFY_SSL: False,
        }

        return await self.async_step_user(self.yaml_config)
