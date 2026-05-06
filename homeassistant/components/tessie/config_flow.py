"""Config Flow for Tessie integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientConnectionError
from tesla_fleet_api.exceptions import InvalidToken, MissingToken, TeslaFleetError
from tesla_fleet_api.tessie import Tessie
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

TESSIE_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})
DESCRIPTION_PLACEHOLDERS = {
    "name": "Tessie",
    "url": "[my.tessie.com/settings/api](https://my.tessie.com/settings/api)",
}


async def _async_validate_access_token(
    hass: HomeAssistant, access_token: str, *, only_active: bool = False
) -> dict[str, str]:
    """Validate a Tessie access token."""
    try:
        await Tessie(async_get_clientsession(hass), access_token).list_vehicles(
            only_active=only_active
        )
    except InvalidToken, MissingToken:
        return {CONF_ACCESS_TOKEN: "invalid_access_token"}
    except ClientConnectionError:
        return {"base": "cannot_connect"}
    except TeslaFleetError:
        return {"base": "unknown"}

    return {}


class TessieConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config Tessie API connection."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Get configuration from the user."""
        errors: dict[str, str] = {}
        if user_input:
            self._async_abort_entries_match(dict(user_input))
            errors = await _async_validate_access_token(
                self.hass, user_input[CONF_ACCESS_TOKEN], only_active=True
            )
            if not errors:
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
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Get update API Key from the user."""
        errors: dict[str, str] = {}

        if user_input:
            errors = await _async_validate_access_token(
                self.hass, user_input[CONF_ACCESS_TOKEN]
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=TESSIE_SCHEMA,
            description_placeholders=DESCRIPTION_PLACEHOLDERS,
            errors=errors,
        )
