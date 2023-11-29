"""Config flow for Epic Games Store integration."""
from __future__ import annotations

import logging
from typing import Any

from epicstore_api import EpicGamesStoreAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_LOCALE, CONF_SUPPORTED_LOCALES, DOMAIN
from .coordinator import not_handle_service_errors
from .helper import get_country_from_locale

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOCALE): vol.In(CONF_SUPPORTED_LOCALES),
    }
)


def get_default_locale(hass: HomeAssistant) -> str:
    """Get default locale code based on Home Assistant config."""
    locale_code = f"{hass.config.language}-{hass.config.country}"
    if locale_code in CONF_SUPPORTED_LOCALES:
        return locale_code
    if hass.config.language in CONF_SUPPORTED_LOCALES:
        return hass.config.language
    return "en-US"


async def validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    api = EpicGamesStoreAPI(
        user_input[CONF_LOCALE], get_country_from_locale(user_input[CONF_LOCALE])
    )
    # pylint: disable-next=protected-access
    api._get_errors = not_handle_service_errors
    data = await hass.async_add_executor_job(api.get_free_games)

    if data.get("errors"):
        _LOGGER.warning(data["errors"])

    try:
        data["data"]["Catalog"]["searchStore"]["elements"]
    except Exception:  # pylint: disable=broad-except
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {
        CONF_LOCALE: user_input[CONF_LOCALE],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Epic Games Store."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        data_schema = self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA,
            user_input or {CONF_LOCALE: get_default_locale(self.hass)},
        )
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=data_schema)

        await self.async_set_unique_id(user_input[CONF_LOCALE])
        self._abort_if_unique_id_configured()

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=f"Epic Games Store {info[CONF_LOCALE]}", data=info
            )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
