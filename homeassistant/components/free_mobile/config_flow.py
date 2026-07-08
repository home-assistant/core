"""Config flow for the Free Mobile integration."""

from http import HTTPStatus
import logging
from typing import Any, override

from freesms import FreeClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, CONF_USERNAME
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, VALIDATION_MESSAGE

_LOGGER = logging.getLogger(__name__)

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
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})
            errors = await self._async_validate_credentials(
                user_input[CONF_USERNAME], user_input[CONF_ACCESS_TOKEN]
            )
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
        )

    async def _async_validate_credentials(
        self, username: str, access_token: str
    ) -> dict[str, str]:
        """Validate credentials by sending a test SMS."""
        try:
            resp = await self.hass.async_add_executor_job(
                lambda: FreeClient(username, access_token).send_sms(VALIDATION_MESSAGE)
            )
        except Exception:
            _LOGGER.exception(
                "Unexpected error while validating Free Mobile credentials"
            )
            return {"base": "unknown"}
        if resp.status_code == HTTPStatus.FORBIDDEN:
            return {"base": "invalid_auth"}
        if resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            return {"base": "server_error"}
        return {}

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
