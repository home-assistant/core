"""Config flow for Radarr."""
from __future__ import annotations

from typing import Any

from aiopyarr import RadarrClient, exceptions
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BASE_PATH,
    CONF_UPCOMING_DAYS,
    CONF_WANTED_MAX_ITEMS,
    DEFAULT_BASE_PATH,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_UPCOMING_DAYS,
    DEFAULT_VERIFY_SSL,
    DEFAULT_WANTED_MAX_ITEMS,
    DOMAIN,
)


async def validate_input(hass: HomeAssistant, data: dict) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    radarr = RadarrClient(
        ipaddress=data[CONF_HOST], api_token=data[CONF_API_KEY], session=async_get_clientsession(hass), port=data[CONF_PORT]
    )
    await radarr.async_get_system_status()


class RadarrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Radarr."""

    VERSION = 1

    def __init__(self):
        """Initialize the flow."""
        self.entry = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return RadarrOptionsFlowHandler(config_entry)

    async def async_step_reauth(self, data: dict[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={"host": self.entry.data[CONF_HOST]},
                data_schema=vol.Schema({}),
                errors={},
            )

        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            if self.entry:
                user_input = {**self.entry.data, **user_input}

            if CONF_VERIFY_SSL not in user_input:
                user_input[CONF_VERIFY_SSL] = DEFAULT_VERIFY_SSL

            try:
                await validate_input(self.hass, user_input)
            except exceptions.ArrAuthenticationException:
                errors = {"base": "invalid_auth"}
            except exceptions.ArrConnectionException:
                errors = {"base": "cannot_connect"}
            except Exception:  # pylint: disable=broad-except
                errors = {"base": "unknown"}
            else:
                if self.entry:
                    return await self._async_reauth_update_entry(user_input)

                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self._get_user_data_schema(user_input)),
            errors=errors,
        )

    async def _async_reauth_update_entry(self, data: dict) -> FlowResult:
        """Update existing config entry."""
        self.hass.config_entries.async_update_entry(self.entry, data=data)
        await self.hass.config_entries.async_reload(self.entry.entry_id)

        return self.async_abort(reason="reauth_successful")

    def _get_user_data_schema(self, user_input: dict[str, Any] | None) -> dict[str, Any]:
        """Get the data schema to display user form."""
        if self.entry:
            return {vol.Required(CONF_API_KEY): str}

        data_schema = {
            vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
            vol.Required(CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")): str,
            vol.Optional(CONF_BASE_PATH, default=user_input.get(CONF_BASE_PATH, DEFAULT_BASE_PATH)): str,
            vol.Optional(CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Optional(CONF_SSL, default=user_input.get(CONF_SSL, DEFAULT_SSL)): bool,
        }

        if self.show_advanced_options:
            data_schema[
                vol.Optional(CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL))
            ] = bool

        return data_schema


class RadarrOptionsFlowHandler(OptionsFlow):
    """Handle Radarr client options."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, int] | None = None) -> FlowResult:
        """Manage Radarr options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_UPCOMING_DAYS,
                default=self.config_entry.options.get(
                    CONF_UPCOMING_DAYS, DEFAULT_UPCOMING_DAYS
                ),
            ): int,
            vol.Optional(
                CONF_WANTED_MAX_ITEMS,
                default=self.config_entry.options.get(
                    CONF_WANTED_MAX_ITEMS, DEFAULT_WANTED_MAX_ITEMS
                ),
            ): int,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
