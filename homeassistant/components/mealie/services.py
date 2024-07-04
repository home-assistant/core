"""Define services for the Mealie integration."""

from dataclasses import asdict
from datetime import date
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
from .const import ATTR_CONFIG_ENTRY_ID, ATTR_END_DATE, ATTR_START_DATE, DOMAIN

SERVICE_GET_MEALPLAN = "get_mealplan"
SERVICE_GET_MEALPLAN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Optional(ATTR_START_DATE): date,
        vol.Optional(ATTR_END_DATE): date,
    }
)


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Mealie integration."""

    async def async_get_mealplan(call: ServiceCall) -> ServiceResponse:
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
        start_date = call.data.get(ATTR_START_DATE, date.today())
        end_date = call.data.get(ATTR_END_DATE, date.today())
        if end_date < start_date:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="end_date_before_start_date",
            )
        client = cast(MealieConfigEntry, entry).runtime_data.client
        mealplans = await client.get_mealplans(start_date, end_date)
        return {"mealplan": [asdict(x) for x in mealplans.items]}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_MEALPLAN,
        async_get_mealplan,
        schema=SERVICE_GET_MEALPLAN_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
