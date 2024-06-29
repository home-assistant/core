"""Define services for the Mealie integration."""

from dataclasses import asdict
from typing import cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError

from . import MealieConfigEntry
from .const import ATTR_CONFIG_ENTRY_ID, DOMAIN

SERVICE_GET_MEALPLAN_TODAY = "get_mealplan_today"
SERVICE_GET_MEALPLAN_TODAY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
    }
)


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Mealie integration."""

    async def async_get_mealplan_today(call: ServiceCall) -> ServiceResponse:
        """Get today's meal plan."""
        if not (
            entry := hass.config_entries.async_get_entry(
                call.data[ATTR_CONFIG_ENTRY_ID]
            )
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="integration_not_found",
                translation_placeholders={"target": DOMAIN},
            )
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_loaded",
                translation_placeholders={"target": entry.title},
            )
        client = cast(MealieConfigEntry, entry).runtime_data.client
        return {
            mealplan.entry_type.value: asdict(mealplan)
            for mealplan in await client.get_mealplan_today()
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_MEALPLAN_TODAY,
        async_get_mealplan_today,
        schema=SERVICE_GET_MEALPLAN_TODAY_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
