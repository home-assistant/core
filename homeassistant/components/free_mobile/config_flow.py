"""Config flow for the Free Mobile integration."""

from collections.abc import Mapping
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, CONF_USERNAME
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="username",
            ),
        ),
        vol.Required(CONF_ACCESS_TOKEN): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
    }
)

STEP_ACCESS_TOKEN_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
    }
)


class FreeMobileConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Free Mobile."""

    def _abort_if_title_configured(self, title: str) -> None:
        """Abort the flow if an entry with the same title already exists.

        Existing YAML setups may have multiple accounts sharing the same
        Free Mobile username (and access token) but a distinct name, each
        exposing its own notify service. Imported entries are deduplicated
        by title rather than by username to preserve that behavior; new
        entries created through the UI are deduplicated by username instead
        (see async_step_user).
        """
        for entry in self._async_current_entries(include_ignore=False):
            if entry.title == title:
                raise AbortFlow("already_configured")

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})
            return self.async_create_entry(
                title=user_input[CONF_USERNAME],
                data=user_input,
            )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import config from yaml."""
        title = import_info.get(CONF_NAME) or import_info[CONF_USERNAME]
        self._abort_if_title_configured(title)
        return self.async_create_entry(
            title=title,
            data={
                CONF_USERNAME: import_info[CONF_USERNAME],
                CONF_ACCESS_TOKEN: import_info[CONF_ACCESS_TOKEN],
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure flow to update the access token."""
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data_updates=user_input,
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_ACCESS_TOKEN_DATA_SCHEMA,
                suggested_values=entry.data,
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        entry = self._get_reauth_entry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data_updates=user_input,
            )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_ACCESS_TOKEN_DATA_SCHEMA,
                suggested_values=entry.data,
            ),
        )
