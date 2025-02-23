"""Config flow for pyLoad integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import CookieJar
from pyloadapi import CannotConnect, InvalidAuth, ParserError, PyLoadAPI
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.URL,
                autocomplete="url",
            ),
        ),
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="username",
            ),
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="username",
            ),
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
    }
)


async def validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> None:
    """Validate the user input and try to connect to PyLoad."""

    session = async_create_clientsession(
        hass,
        user_input[CONF_VERIFY_SSL],
        cookie_jar=CookieJar(unsafe=True),
    )
    pyload = PyLoadAPI(
        session,
        api_url=user_input[CONF_URL],
        username=user_input[CONF_USERNAME],
        password=user_input[CONF_PASSWORD],
    )

    await pyload.login()


class PyLoadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pyLoad."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = URL(user_input[CONF_URL])
            self._async_abort_entries_match(
                {
                    CONF_HOST: url.host,
                    CONF_PORT: url.port,
                }
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
                title = DEFAULT_NAME
                data = {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_HOST: url.host,
                    CONF_PORT: url.port,
                    CONF_SSL: (url.scheme == "https"),
                    CONF_PATH: url.path,
                    CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                }
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}
        reauth_entry = self._get_reauth_entry()
        reauth_data = {
            **reauth_entry.data,
            CONF_URL: URL.build(
                scheme="https" if reauth_entry.data[CONF_SSL] else "http",
                host=reauth_entry.data[CONF_HOST],
                port=reauth_entry.data[CONF_PORT],
                path=reauth_entry.data.get(CONF_PATH, "/"),
            ),
        }
        if user_input is not None:
            try:
                await validate_input(self.hass, {**reauth_data, **user_input})
            except (CannotConnect, ParserError):
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA,
                {
                    CONF_USERNAME: user_input[CONF_USERNAME]
                    if user_input is not None
                    else reauth_data[CONF_USERNAME]
                },
            ),
            description_placeholders={CONF_NAME: reauth_data[CONF_USERNAME]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfiguration flow."""
        errors = {}
        reconfig_entry = self._get_reconfigure_entry()

        if user_input is not None:
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
                url = URL(user_input[CONF_URL])
                data = {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_HOST: url.host,
                    CONF_PORT: url.port,
                    CONF_SSL: (url.scheme == "https"),
                    CONF_PATH: url.path,
                    CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                }
                return self.async_update_reload_and_abort(
                    reconfig_entry,
                    data=data,
                    reload_even_if_entry_is_unchanged=False,
                )
        suggested_values = (
            user_input
            if user_input
            else {
                **reconfig_entry.data,
                CONF_URL: URL.build(
                    scheme="https" if reconfig_entry.data[CONF_SSL] else "http",
                    host=reconfig_entry.data[CONF_HOST],
                    port=reconfig_entry.data[CONF_PORT],
                    path=reconfig_entry.data.get(CONF_PATH, "/"),
                ).human_repr(),
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                suggested_values,
            ),
            description_placeholders={CONF_NAME: reconfig_entry.data[CONF_USERNAME]},
            errors=errors,
        )
