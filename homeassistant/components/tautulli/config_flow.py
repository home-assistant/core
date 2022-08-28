"""Config flow for Tautulli."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pytautulli import PyTautulli, PyTautulliException, exceptions
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_NAME, DOMAIN


class TautulliConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tautulli."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors = {}
        if user_input is not None:
            if (error := await self.validate_input(user_input)) is None:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )
            errors["base"] = error

        user_input = user_input or {}
        data_schema = {
            vol.Required(CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")): str,
            vol.Required(CONF_URL, default=user_input.get(CONF_URL, "")): str,
            vol.Optional(
                CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL, True)
            ): bool,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=errors or {},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle a reauthorization flow request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        errors = {}
        if user_input is not None and (
            entry := self.hass.config_entries.async_get_entry(self.context["entry_id"])
        ):
            _input = {**entry.data, CONF_API_KEY: user_input[CONF_API_KEY]}
            if (error := await self.validate_input(_input)) is None:
                self.hass.config_entries.async_update_entry(entry, data=_input)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def validate_input(self, user_input: dict[str, Any]) -> str | None:
        """Try connecting to Tautulli."""
        try:
            api_client = PyTautulli(
                api_token=user_input[CONF_API_KEY],
                url=user_input[CONF_URL],
                session=async_get_clientsession(
                    self.hass, user_input.get(CONF_VERIFY_SSL, True)
                ),
                verify_ssl=user_input.get(CONF_VERIFY_SSL, True),
            )
            await api_client.async_get_server_info()
        except exceptions.PyTautulliConnectionException:
            return "cannot_connect"
        except exceptions.PyTautulliAuthenticationException:
            return "invalid_auth"
        except PyTautulliException:
            return "unknown"
        return None
