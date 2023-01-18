"""Config flow for DuckDNS integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from . import update_duckdns
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("domain"): str,
        vol.Required("access_token"): str,
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass."""

    def __init__(self) -> None:
        """Initialize."""

    async def authenticate(
        self, hass: HomeAssistant, domain: str, access_token: str
    ) -> bool:
        """Test if we can authenticate with the host."""
        session = async_get_clientsession(hass)
        return await update_duckdns(session, domain, access_token)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    hub = PlaceholderHub()

    if not await hub.authenticate(hass, data["domain"], data["access_token"]):
        raise InvalidAuth

    return {"title": "DuckDNS"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for duckdns."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(f"{DOMAIN}_{user_input['domain']}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input["domain"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        async_create_issue(
            self.hass,
            DOMAIN,
            "deprecated_yaml",
            breaks_in_ha_version="2023.4.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
        )
        return await self.async_step_user(user_input)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
