"""Config Flow for Tessie integration."""
from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from aiohttp import ClientConnectionError, ClientResponseError
from tessie_api import get_state_of_all_vehicles
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

TESSIE_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})


class TessieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Tessie API connection."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> FlowResult:
        """Get configuration from the user."""
        errors: dict[str, str] = {}
        if user_input and CONF_ACCESS_TOKEN in user_input:
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
            errors=errors,
        )
