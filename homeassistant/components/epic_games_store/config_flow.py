"""Config flow for Epic Games Store integration."""

from __future__ import annotations

import logging
from typing import Any

from epicstore_api import EpicGamesStoreAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    CountrySelector,
    LanguageSelector,
    LanguageSelectorConfig,
)

from .const import DOMAIN, SUPPORTED_LANGUAGES

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LANGUAGE): LanguageSelector(
            LanguageSelectorConfig(languages=SUPPORTED_LANGUAGES)
        ),
        vol.Required(CONF_COUNTRY): CountrySelector(),
    }
)


def get_default_language(hass: HomeAssistant) -> str | None:
    """Get default language code based on Home Assistant config."""
    language_code = f"{hass.config.language}-{hass.config.country}"
    if language_code in SUPPORTED_LANGUAGES:
        return language_code
    if hass.config.language in SUPPORTED_LANGUAGES:
        return hass.config.language
    return None


async def validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    api = EpicGamesStoreAPI(user_input[CONF_LANGUAGE], user_input[CONF_COUNTRY])
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
            user_input
            or {
                CONF_LANGUAGE: get_default_language(self.hass),
                CONF_COUNTRY: self.hass.config.country,
            },
        )
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=data_schema)

        await self.async_set_unique_id(
            f"freegames-{user_input[CONF_LANGUAGE]}-{user_input[CONF_COUNTRY]}"
        )
        self._abort_if_unique_id_configured()

        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=f"Epic Games Store - Free Games ({user_input[CONF_LANGUAGE]}-{user_input[CONF_COUNTRY]})",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
