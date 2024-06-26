"""Config flow for pyLoad integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

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
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import PyLoadConfigEntry
from .const import DEFAULT_HOST, DEFAULT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SSL, default=False): cv.boolean,
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

    url = (
        f"{"https" if user_input[CONF_SSL] else "http"}://"
        f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}/"
    )
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
    config_entry: PyLoadConfigEntry | None

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
                title = user_input.pop(CONF_NAME, DEFAULT_NAME)
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import config from yaml."""

        config = {
            CONF_NAME: import_info.get(CONF_NAME),
            CONF_HOST: import_info.get(CONF_HOST, DEFAULT_HOST),
            CONF_PASSWORD: import_info.get(CONF_PASSWORD, ""),
            CONF_PORT: import_info.get(CONF_PORT, DEFAULT_PORT),
            CONF_SSL: import_info.get(CONF_SSL, False),
            CONF_USERNAME: import_info.get(CONF_USERNAME, ""),
            CONF_VERIFY_SSL: False,
        }

        result = await self.async_step_user(config)

        if errors := result.get("errors"):
            return self.async_abort(reason=errors["base"])
        return result

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}

        if TYPE_CHECKING:
            assert self.config_entry

        if user_input is not None:
            new_input = self.config_entry.data | user_input
            try:
                await validate_input(self.hass, new_input)
            except (CannotConnect, ParserError):
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self.config_entry, data=new_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA,
                {
                    CONF_USERNAME: user_input[CONF_USERNAME]
                    if user_input is not None
                    else self.config_entry.data[CONF_USERNAME]
                },
            ),
            description_placeholders={CONF_NAME: self.config_entry.data[CONF_USERNAME]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform a reconfiguration."""
        self.config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfiguration flow."""
        errors = {}

        if TYPE_CHECKING:
            assert self.config_entry

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
                return self.async_update_reload_and_abort(
                    self.config_entry,
                    data=user_input,
                    reload_even_if_entry_is_unchanged=False,
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input or self.config_entry.data,
            ),
            description_placeholders={CONF_NAME: self.config_entry.data[CONF_USERNAME]},
            errors=errors,
        )
