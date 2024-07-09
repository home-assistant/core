"""Define services for the Mealie integration."""

from dataclasses import asdict
from datetime import date
from typing import cast

from aiomealie.exceptions import MealieConnectionError, MealieNotFoundError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_END_DATE,
    ATTR_RECIPE_ID,
    ATTR_START_DATE,
    DOMAIN,
)
from .coordinator import MealieConfigEntry

SERVICE_GET_MEALPLAN = "get_mealplan"
SERVICE_GET_MEALPLAN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Optional(ATTR_START_DATE): date,
        vol.Optional(ATTR_END_DATE): date,
    }
)

SERVICE_GET_RECIPE = "get_recipe"
SERVICE_GET_RECIPE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Required(ATTR_RECIPE_ID): str,
    }
)


def async_get_entry(hass: HomeAssistant, config_entry_id: str) -> MealieConfigEntry:
    """Get the Mealie config entry."""
    if not (entry := hass.config_entries.async_get_entry(config_entry_id)):
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
    return cast(MealieConfigEntry, entry)


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Mealie integration."""

    async def async_get_mealplan(call: ServiceCall) -> ServiceResponse:
        """Get the mealplan for a specific range."""
        entry = async_get_entry(hass, call.data[ATTR_CONFIG_ENTRY_ID])
        start_date = call.data.get(ATTR_START_DATE, date.today())
        end_date = call.data.get(ATTR_END_DATE, date.today())
        if end_date < start_date:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="end_date_before_start_date",
            )
        client = cast(MealieConfigEntry, entry).runtime_data.client
        try:
            mealplans = await client.get_mealplans(start_date, end_date)
        except MealieConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from err
        return {"mealplan": [asdict(x) for x in mealplans.items]}

    async def async_get_recipe(call: ServiceCall) -> ServiceResponse:
        """Get a recipe."""
        entry = async_get_entry(hass, call.data[ATTR_CONFIG_ENTRY_ID])
        recipe_id = call.data[ATTR_RECIPE_ID]
        client = entry.runtime_data.client
        try:
            recipe = await client.get_recipe(recipe_id)
        except MealieConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from err
        except MealieNotFoundError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="recipe_not_found",
                translation_placeholders={"recipe_id": recipe_id},
            ) from err
        return {"recipe": asdict(recipe)}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_MEALPLAN,
        async_get_mealplan,
        schema=SERVICE_GET_MEALPLAN_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_RECIPE,
        async_get_recipe,
        schema=SERVICE_GET_RECIPE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
