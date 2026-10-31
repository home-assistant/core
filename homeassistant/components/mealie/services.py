"""Define services for the Mealie integration."""

from dataclasses import asdict
from enum import StrEnum

from aiomealie import (
    MealieConnectionError,
    MealieNotFoundError,
    MealieValidationError,
    MealplanEntryType,
    RegisteredParser,
)
from awesomeversion import AwesomeVersion
import probatio

from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType
from homeassistant.util import dt as dt_util

from .const import CONF_PARSER, DEFAULT_PARSER, DOMAIN, MINIMUM_PARSER_CONFIDENCE
from .coordinator import MealieConfigEntry


class MealieService(StrEnum):
    """Service names for Mealie."""

    ADD_INGREDIENT = "add_ingredient"
    DELETE_MEALPLAN = "delete_mealplan"
    GET_MEALPLAN = "get_mealplan"
    GET_RECIPE = "get_recipe"
    GET_RECIPES = "get_recipes"
    GET_SHOPPING_LIST_ITEMS = "get_shopping_list_items"
    IMPORT_RECIPE = "import_recipe"
    PARSE_INGREDIENT = "parse_ingredient"
    SET_MEALPLAN = "set_mealplan"
    SET_RANDOM_MEALPLAN = "set_random_mealplan"
    UPDATE_MEALPLAN = "update_mealplan"


class MealieServiceArgument(StrEnum):
    """Service argument names for Mealie."""

    DATE = "date"
    END_DATE = "end_date"
    ENTRY_TYPE = "entry_type"
    FOOD_ID = "food_id"
    INCLUDE_TAGS = "include_tags"
    INGREDIENT = "ingredient"
    MEALPLAN_ID = "mealplan_id"
    NOTE = "note"
    NOTE_TEXT = "note_text"
    NOTE_TITLE = "note_title"
    QUANTITY = "quantity"
    RECIPE_ID = "recipe_id"
    RESULT_LIMIT = "result_limit"
    SEARCH_TERMS = "search_terms"
    START_DATE = "start_date"
    UNIT_ID = "unit_id"
    URL = "url"


SERVICE_ADD_INGREDIENT_SCHEMA: VolDictType = {
    probatio.Optional(MealieServiceArgument.FOOD_ID): str,
    probatio.Optional(MealieServiceArgument.NOTE): str,
    probatio.Optional(MealieServiceArgument.UNIT_ID): str,
    probatio.Optional(MealieServiceArgument.QUANTITY): cv.positive_float,
}

SERVICE_GET_MEALPLAN_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): str,
        probatio.Optional(MealieServiceArgument.START_DATE): cv.date,
        probatio.Optional(MealieServiceArgument.END_DATE): cv.date,
    }
)

SERVICE_GET_RECIPE_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): str,
        probatio.Required(MealieServiceArgument.RECIPE_ID): str,
    }
)

SERVICE_GET_RECIPES_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): str,
        probatio.Optional(MealieServiceArgument.SEARCH_TERMS): str,
        probatio.Optional(MealieServiceArgument.RESULT_LIMIT): int,
    }
)


SERVICE_IMPORT_RECIPE_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): str,
        probatio.Required(MealieServiceArgument.URL): str,
        probatio.Optional(MealieServiceArgument.INCLUDE_TAGS): bool,
    }
)

SERVICE_SET_RANDOM_MEALPLAN_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): str,
        probatio.Required(MealieServiceArgument.DATE): cv.date,
        probatio.Required(MealieServiceArgument.ENTRY_TYPE): probatio.In(
            [x.lower() for x in MealplanEntryType]
        ),
    }
)

SERVICE_SET_MEALPLAN_SCHEMA = probatio.Any(
    probatio.Schema(
        {
            probatio.Required(ATTR_CONFIG_ENTRY_ID): str,
            probatio.Required(MealieServiceArgument.DATE): cv.date,
            probatio.Required(MealieServiceArgument.ENTRY_TYPE): probatio.In(
                [x.lower() for x in MealplanEntryType]
            ),
            probatio.Required(MealieServiceArgument.RECIPE_ID): str,
        }
    ),
    probatio.Schema(
        {
            probatio.Required(ATTR_CONFIG_ENTRY_ID): str,
            probatio.Required(MealieServiceArgument.DATE): cv.date,
            probatio.Required(MealieServiceArgument.ENTRY_TYPE): probatio.In(
                [x.lower() for x in MealplanEntryType]
            ),
            probatio.Required(MealieServiceArgument.NOTE_TITLE): str,
            probatio.Optional(MealieServiceArgument.NOTE_TEXT): str,
        }
    ),
)
SERVICE_DELETE_MEALPLAN_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): str,
        probatio.Required(MealieServiceArgument.MEALPLAN_ID): probatio.Any(str, int),
    }
)
SERVICE_UPDATE_MEALPLAN_SCHEMA = probatio.Any(
    probatio.Schema(
        {
            probatio.Required(ATTR_CONFIG_ENTRY_ID): str,
            probatio.Required(MealieServiceArgument.MEALPLAN_ID): probatio.Any(
                str, int
            ),
            probatio.Required(MealieServiceArgument.DATE): cv.date,
            probatio.Required(MealieServiceArgument.ENTRY_TYPE): probatio.In(
                [x.lower() for x in MealplanEntryType]
            ),
            probatio.Required(MealieServiceArgument.RECIPE_ID): str,
        }
    ),
    probatio.Schema(
        {
            probatio.Required(ATTR_CONFIG_ENTRY_ID): str,
            probatio.Required(MealieServiceArgument.MEALPLAN_ID): probatio.Any(
                str, int
            ),
            probatio.Required(MealieServiceArgument.DATE): cv.date,
            probatio.Required(MealieServiceArgument.ENTRY_TYPE): probatio.In(
                [x.lower() for x in MealplanEntryType]
            ),
            probatio.Required(MealieServiceArgument.NOTE_TITLE): str,
            probatio.Optional(MealieServiceArgument.NOTE_TEXT): str,
        }
    ),
)
SERVICE_PARSE_INGREDIENT_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): str,
        probatio.Required(MealieServiceArgument.INGREDIENT): str,
    }
)


def _validate_mealplan_type(version: AwesomeVersion, entry_type: str) -> None:
    """Validate mealplan entry type, if prior to 3.7.0."""

    if (
        version.valid
        and version < AwesomeVersion("v3.7.0")
        and entry_type
        not in {
            MealplanEntryType.BREAKFAST.value,
            MealplanEntryType.DINNER.value,
            MealplanEntryType.LUNCH.value,
            MealplanEntryType.SIDE.value,
        }
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_mealplan_entry_type",
            translation_placeholders={"mealplan_type": entry_type},
        )


async def _async_get_mealplan(call: ServiceCall) -> ServiceResponse:
    """Get the mealplan for a specific range."""
    entry: MealieConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    start_date = call.data.get(MealieServiceArgument.START_DATE, dt_util.now().date())
    end_date = call.data.get(MealieServiceArgument.END_DATE, dt_util.now().date())
    if end_date < start_date:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="end_date_before_start_date",
        )
    client = entry.runtime_data.client
    try:
        mealplans = await client.get_mealplans(start_date, end_date)
    except MealieConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from err
    return {"mealplan": [asdict(x) for x in mealplans.items]}


async def _async_get_recipe(call: ServiceCall) -> ServiceResponse:
    """Get a recipe."""
    entry: MealieConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    recipe_id = call.data[MealieServiceArgument.RECIPE_ID]
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


async def _async_get_recipes(call: ServiceCall) -> ServiceResponse:
    """Get recipes."""
    entry: MealieConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    search_terms = call.data.get(MealieServiceArgument.SEARCH_TERMS)
    result_limit = call.data.get(MealieServiceArgument.RESULT_LIMIT, 10)
    client = entry.runtime_data.client
    try:
        recipes = await client.get_recipes(search=search_terms, per_page=result_limit)
    except MealieConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from err
    except MealieNotFoundError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_recipes_found",
        ) from err
    return {"recipes": asdict(recipes)}


async def _async_import_recipe(call: ServiceCall) -> ServiceResponse:
    """Import a recipe."""
    entry: MealieConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    url = call.data[MealieServiceArgument.URL]
    include_tags = call.data.get(MealieServiceArgument.INCLUDE_TAGS, False)
    client = entry.runtime_data.client
    try:
        recipe = await client.import_recipe(url, include_tags)
    except MealieValidationError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="could_not_import_recipe",
        ) from err
    except MealieConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from err
    if call.return_response:
        return {"recipe": asdict(recipe)}
    return None


async def _async_set_random_mealplan(call: ServiceCall) -> ServiceResponse:
    """Set a random mealplan."""
    entry: MealieConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    mealplan_date = call.data[MealieServiceArgument.DATE]
    entry_type = MealplanEntryType(call.data[MealieServiceArgument.ENTRY_TYPE])
    client = entry.runtime_data.client

    _validate_mealplan_type(entry.runtime_data.version, entry_type.value)

    try:
        mealplan = await client.random_mealplan(mealplan_date, entry_type)
    except MealieConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from err
    if call.return_response:
        return {"mealplan": asdict(mealplan)}
    return None


async def _async_set_mealplan(call: ServiceCall) -> ServiceResponse:
    """Set a mealplan."""
    entry: MealieConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    mealplan_date = call.data[MealieServiceArgument.DATE]
    entry_type = MealplanEntryType(call.data[MealieServiceArgument.ENTRY_TYPE])
    client = entry.runtime_data.client

    _validate_mealplan_type(entry.runtime_data.version, entry_type.value)

    try:
        mealplan = await client.set_mealplan(
            mealplan_date,
            entry_type,
            recipe_id=call.data.get(MealieServiceArgument.RECIPE_ID),
            note_title=call.data.get(MealieServiceArgument.NOTE_TITLE),
            note_text=call.data.get(MealieServiceArgument.NOTE_TEXT),
        )
    except MealieConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from err
    if call.return_response:
        return {"mealplan": asdict(mealplan)}
    return None


async def _async_delete_mealplan(call: ServiceCall) -> ServiceResponse:
    """Delete a mealplan."""
    entry: MealieConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    mealplan_id = int(call.data[MealieServiceArgument.MEALPLAN_ID])
    client = entry.runtime_data.client

    try:
        await client.delete_mealplan(
            mealplan_id,
        )
    except MealieConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from err
    except MealieNotFoundError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="mealplan_not_found",
            translation_placeholders={"mealplan_id": str(mealplan_id)},
        ) from err
    return None


async def _async_update_mealplan(call: ServiceCall) -> ServiceResponse:
    """Update a mealplan."""
    entry: MealieConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    mealplan_id = int(call.data[MealieServiceArgument.MEALPLAN_ID])
    mealplan_date = call.data[MealieServiceArgument.DATE]
    entry_type = MealplanEntryType(call.data[MealieServiceArgument.ENTRY_TYPE])
    client = entry.runtime_data.client

    _validate_mealplan_type(entry.runtime_data.version, entry_type.value)

    try:
        mealplan = await client.update_mealplan(
            mealplan_id,
            mealplan_date,
            entry_type,
            recipe_id=call.data.get(MealieServiceArgument.RECIPE_ID),
            note_title=call.data.get(MealieServiceArgument.NOTE_TITLE),
            note_text=call.data.get(MealieServiceArgument.NOTE_TEXT),
        )
    except MealieConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from err
    except MealieNotFoundError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="mealplan_not_found",
            translation_placeholders={"mealplan_id": str(mealplan_id)},
        ) from err
    if call.return_response:
        return {"mealplan": asdict(mealplan)}
    return None


async def _async_parse_ingredient(call: ServiceCall) -> ServiceResponse:
    """Parse an ingredient using the Mealie parser with the match method chosen in options."""
    entry: MealieConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    ingredient = call.data[MealieServiceArgument.INGREDIENT]
    client = entry.runtime_data.client
    parser = RegisteredParser(entry.options.get(CONF_PARSER, DEFAULT_PARSER))

    try:
        result = await client.parse_ingredient(ingredient, parser)
    except MealieConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from err
    if not result or not result.confidence:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="could_not_parse_ingredient",
        )

    result_dict = asdict(result)
    # Add flag to indicate whether the ingredient has acceptable confidence to
    # be added as an ingredient in the to-do list add_item method.
    result_dict["confidence"]["acceptable_confidence"] = (
        result.confidence.average or 0.0
    ) >= MINIMUM_PARSER_CONFIDENCE
    return result_dict


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Mealie integration."""

    hass.services.async_register(
        DOMAIN,
        MealieService.GET_MEALPLAN,
        _async_get_mealplan,
        schema=SERVICE_GET_MEALPLAN_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        MealieService.GET_RECIPE,
        _async_get_recipe,
        schema=SERVICE_GET_RECIPE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        MealieService.GET_RECIPES,
        _async_get_recipes,
        schema=SERVICE_GET_RECIPES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        MealieService.IMPORT_RECIPE,
        _async_import_recipe,
        schema=SERVICE_IMPORT_RECIPE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        MealieService.SET_RANDOM_MEALPLAN,
        _async_set_random_mealplan,
        schema=SERVICE_SET_RANDOM_MEALPLAN_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        MealieService.SET_MEALPLAN,
        _async_set_mealplan,
        schema=SERVICE_SET_MEALPLAN_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        MealieService.DELETE_MEALPLAN,
        _async_delete_mealplan,
        schema=SERVICE_DELETE_MEALPLAN_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        MealieService.UPDATE_MEALPLAN,
        _async_update_mealplan,
        schema=SERVICE_UPDATE_MEALPLAN_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        MealieService.PARSE_INGREDIENT,
        _async_parse_ingredient,
        schema=SERVICE_PARSE_INGREDIENT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MealieService.ADD_INGREDIENT,
        entity_domain=TODO_DOMAIN,
        schema=SERVICE_ADD_INGREDIENT_SCHEMA,
        func="async_add_ingredient",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MealieService.GET_SHOPPING_LIST_ITEMS,
        entity_domain=TODO_DOMAIN,
        schema=None,
        func="async_get_shopping_list_items",
        supports_response=SupportsResponse.ONLY,
    )
