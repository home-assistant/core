"""Config flow for Overseerr integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from overseerr_api import ApiClient, AuthApi, Configuration
from overseerr_api.exceptions import OpenApiException
from pydantic_core import ValidationError
from urllib3.exceptions import MaxRetryError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OverseerrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Overseerr."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self.entry: ConfigEntry | None = None

    async def async_step_reauth(self, _: Mapping[str, Any]) -> FlowResult:
        """Handle re-auth of Overseerr configuration."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if user_input is not None:
            return await self.async_step_user()

        self._set_confirm_only()
        return self.async_show_form(step_id="reauth_confirm")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            user_input = dict(self.entry.data) if self.entry else None

        else:
            try:
                if result := await validate_input(self.hass, user_input):
                    user_input[CONF_API_KEY] = result[1]
            except ValidationError:
                errors = {"base": "validation_error"}
            except (OpenApiException, MaxRetryError):
                errors = {"base": "open_api_exception"}
            if not errors:
                if self.entry:
                    self.hass.config_entries.async_update_entry(
                        self.entry, data=user_input
                    )
                    await self.hass.config_entries.async_reload(self.entry.entry_id)

                    return self.async_abort(reason="reauth_successful")

                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL, default=user_input.get(CONF_URL, DEFAULT_URL)
                    ): str,
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[str, str, str] | None:
    """Validate the user input allows us to connect to Overseerr."""
    overseerr_config = Configuration(
        api_key={"apiKey": data.get(CONF_API_KEY, "")},
        host=data[CONF_URL],
    )

    overseerr_client = ApiClient(overseerr_config)
    auth_api = AuthApi(overseerr_client)

    await hass.async_add_executor_job(auth_api.auth_me_get)

    return None
