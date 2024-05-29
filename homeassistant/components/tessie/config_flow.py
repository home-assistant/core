"""Config Flow for Tessie integration."""

from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from aiohttp import ClientConnectionError, ClientResponseError
from tessie_api import get_state_of_all_vehicles
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import TessieConfigEntry
from .const import DOMAIN

TESSIE_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})
DESCRIPTION_PLACEHOLDERS = {
    "url": "[my.tessie.com/settings/api](https://my.tessie.com/settings/api)"
}


class TessieConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config Tessie API connection."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._reauth_entry: TessieConfigEntry | None = None

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Get configuration from the user."""
        errors: dict[str, str] = {}
        if user_input:
            try:
                await get_state_of_all_vehicles(
                    session=async_get_clientsession(self.hass),
                    api_key=user_input[CONF_ACCESS_TOKEN],
                    only_active=True,
                )
            except ClientResponseError as e:
                if e.status == HTTPStatus.UNAUTHORIZED:
                    errors[CONF_ACCESS_TOKEN] = "invalid_access_token"
                else:
                    errors["base"] = "unknown"
            except ClientConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Tessie",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=TESSIE_SCHEMA,
            description_placeholders=DESCRIPTION_PLACEHOLDERS,
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-auth."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Get update API Key from the user."""
        errors: dict[str, str] = {}
        assert self._reauth_entry
        if user_input:
            try:
                await get_state_of_all_vehicles(
                    session=async_get_clientsession(self.hass),
                    api_key=user_input[CONF_ACCESS_TOKEN],
                )
            except ClientResponseError as e:
                if e.status == HTTPStatus.UNAUTHORIZED:
                    errors[CONF_ACCESS_TOKEN] = "invalid_access_token"
                else:
                    errors["base"] = "unknown"
            except ClientConnectionError:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=user_input
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=TESSIE_SCHEMA,
            description_placeholders=DESCRIPTION_PLACEHOLDERS,
            errors=errors,
        )
