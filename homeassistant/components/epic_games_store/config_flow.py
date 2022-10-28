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

from .const import (
    CONF_COUNTRY,
    CONF_LOCALE,
    CONF_SUPPORTED_COUNTRIES,
    CONF_SUPPORTED_LANGUAGES,
    CONF_SUPPORTED_LOCALES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOCALE): vol.In(CONF_SUPPORTED_LANGUAGES),
        # vol.Required(CONF_LOCALE): vol.In(CONF_SUPPORTED_LOCALES),
        # vol.Required(CONF_COUNTRY): vol.In(CONF_SUPPORTED_COUNTRIES),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    # TODO: something is odd --> why locale as country passes here but not into init ?
    api = EpicGamesStoreAPI(data[CONF_LOCALE], data[CONF_LOCALE])
    # api = EpicGamesStoreAPI(data[CONF_LOCALE], data[CONF_COUNTRY])

    if not await hass.async_add_executor_job(api.get_free_games):
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {
        "title": f"Epic Games Store {data[CONF_LOCALE]}",
        CONF_LOCALE: data[CONF_LOCALE],
        # CONF_COUNTRY: data[CONF_COUNTRY],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Epic Games Store."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        await self.async_set_unique_id(user_input[CONF_LOCALE])
        # await self.async_set_unique_id(f"{info[CONF_LOCALE]}-{info[CONF_COUNTRY]}")
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
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
