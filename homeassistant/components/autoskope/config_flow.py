"""Config flow for the Autoskope integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from autoskope_client.api import AutoskopeApi
from autoskope_client.models import CannotConnect, InvalidAuth
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import section
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DEFAULT_HOST, DOMAIN, SECTION_ADVANCED_SETTINGS

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(SECTION_ADVANCED_SETTINGS): section(
            vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.URL)
                    ),
                }
            ),
            {"collapsed": True},
        ),
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class AutoskopeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Autoskope."""

    VERSION = 1

    async def _async_validate_credentials(
        self, host: str, username: str, password: str, errors: dict[str, str]
    ) -> bool:
        """Validate credentials against the Autoskope API."""
        try:
            async with AutoskopeApi(
                host=host,
                username=username,
                password=password,
            ):
                pass
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        else:
            return True
        return False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].lower()
            host = user_input[SECTION_ADVANCED_SETTINGS][CONF_HOST].lower()

            try:
                cv.url(host)
            except vol.Invalid:
                errors["base"] = "invalid_url"

            if not errors:
                await self.async_set_unique_id(f"{username}@{host}")
                self._abort_if_unique_id_configured()

                if await self._async_validate_credentials(
                    host, username, user_input[CONF_PASSWORD], errors
                ):
                    return self.async_create_entry(
                        title=f"Autoskope ({username})",
                        data={
                            CONF_USERNAME: username,
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_HOST: host,
                        },
                    )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with new credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()

            if await self._async_validate_credentials(
                reauth_entry.data[CONF_HOST],
                reauth_entry.data[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                errors,
            ):
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )
