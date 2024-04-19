"""Config flow for Epic Games Store integration."""

from __future__ import annotations

import logging
from typing import Any

from epicstore_api import EpicGamesStoreAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_LANGUAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import LanguageSelector, LanguageSelectorConfig

from .const import DOMAIN, SUPPORTED_LANGUAGES
from .helper import get_country_from_language

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LANGUAGE): LanguageSelector(
            LanguageSelectorConfig(languages=SUPPORTED_LANGUAGES)
        ),
    }
)


def get_default_language(hass: HomeAssistant) -> str:
    """Get default language code based on Home Assistant config."""
    language_code = f"{hass.config.language}-{hass.config.country}"
    if language_code in SUPPORTED_LANGUAGES:
        return language_code
    if hass.config.language in SUPPORTED_LANGUAGES:
        return hass.config.language
    return "en-US"


async def validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    api = EpicGamesStoreAPI(
        user_input[CONF_LANGUAGE], get_country_from_language(user_input[CONF_LANGUAGE])
    )
    data = await hass.async_add_executor_job(api.get_free_games)

    if data.get("errors"):
        _LOGGER.warning(data["errors"])

    assert data["data"]["Catalog"]["searchStore"]["elements"]


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Epic Games Store."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        data_schema = self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA,
            user_input or {CONF_LANGUAGE: get_default_language(self.hass)},
        )
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=data_schema)

        await self.async_set_unique_id(user_input[CONF_LANGUAGE])
        self._abort_if_unique_id_configured()

        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=f"Epic Games Store {user_input[CONF_LANGUAGE]}", data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
