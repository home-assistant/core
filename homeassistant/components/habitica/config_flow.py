"""Config flow for habitica integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientResponseError
from habitipy.aio import HabitipyAsync
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_URL
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_API_USER, DEFAULT_URL, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_USER): str,
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_URL, default=DEFAULT_URL): str,
    }
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, str]) -> dict[str, str]:
    """Validate the user input allows us to connect."""

    websession = async_get_clientsession(hass)
    api = await hass.async_add_executor_job(
        HabitipyAsync,
        {
            "login": data[CONF_API_USER],
            "password": data[CONF_API_KEY],
            "url": data[CONF_URL] or DEFAULT_URL,
        },
    )
    try:
        await api.user.get(session=websession)
        return {
            "title": f"{data.get('name', 'Default username')}",
            CONF_API_USER: data[CONF_API_USER],
        }
    except ClientResponseError as ex:
        raise InvalidAuth from ex


class HabiticaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for habitica."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors = {"base": "invalid_credentials"}
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors = {"base": "unknown"}
            else:
                await self.async_set_unique_id(info[CONF_API_USER])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import habitica config from configuration.yaml."""

        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            is_fixable=False,
            breaks_in_ha_version="2024.11.0",
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Habitica",
            },
        )
        return await self.async_step_user(import_data)


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
