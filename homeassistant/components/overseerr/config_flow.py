"""Config flow for Overseerr integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientConnectorError
from overseerr import ApiClient, Configuration, RequestApi, exceptions
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__package__)


class OverseerrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Overseerr."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self.entry: ConfigEntry | None = None

    async def async_step_reauth(self, _: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
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
            except exceptions.UnauthorizedException:
                errors = {"base": "invalid_auth"}
            except ClientConnectorError:
                errors = {"base": "cannot_connect"}
            except exceptions.OpenApiException:
                errors = {"base": "unknown"}
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
                    vol.Optional(CONF_API_KEY): str,
                    vol.Optional(
                        CONF_VERIFY_SSL,
                        default=user_input.get(CONF_VERIFY_SSL, False),
                    ): bool,
                }
            ),
            errors=errors,
        )


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[str, str, str] | None:
    """Validate the user input allows us to connect."""
    host_configuration = Configuration(
        api_key=data.get(CONF_API_KEY, ""),
        ssl_ca_cert=data[CONF_VERIFY_SSL],
        host=data[CONF_URL],
    )

    async with ApiClient(configuration=host_configuration) as overseerr_api_client:
        request_api = RequestApi(overseerr_api_client)
        await request_api.request_count_get()

    return None
