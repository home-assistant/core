"""Config flow for Opower integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from opower import CannotConnect, InvalidAuth, Opower, get_supported_utility_names
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_TOTP_SECRET, CONF_UTILITY, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_UTILITY): vol.In(
            get_supported_utility_names(supports_mfa=True)
        ),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_TOTP_SECRET): str,
    }
)


async def _validate_login(
    hass: HomeAssistant, login_data: dict[str, str]
) -> dict[str, str]:
    """Validate login data and return any errors."""
    api = Opower(
        async_create_clientsession(hass),
        login_data[CONF_UTILITY],
        login_data[CONF_USERNAME],
        login_data[CONF_PASSWORD],
        login_data.get(CONF_TOTP_SECRET, None),
    )
    errors: dict[str, str] = {}
    try:
        await api.async_login()
    except InvalidAuth:
        errors["base"] = "invalid_auth"
    except CannotConnect:
        errors["base"] = "cannot_connect"
    return errors


class OpowerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Opower."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize a new OpowerConfigFlow."""
        self.reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_UTILITY: user_input[CONF_UTILITY],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                }
            )
            errors = await _validate_login(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_UTILITY]} ({user_input[CONF_USERNAME]})",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        assert self.reauth_entry
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**self.reauth_entry.data, **user_input}
            errors = await _validate_login(self.hass, data)
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry, data=data
                )
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): self.reauth_entry.data[CONF_USERNAME],
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_TOTP_SECRET): str,
                }
            ),
            errors=errors,
        )
