"""Tests for the Mealie services."""

from datetime import date
from unittest.mock import AsyncMock

from aiomealie import (
    About,
    MealieConnectionError,
    MealieNotFoundError,
    MealieValidationError,
    MealplanEntryType,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mealie.const import (
    ATTR_END_DATE,
    ATTR_ENTRY_TYPE,
    ATTR_INCLUDE_TAGS,
    ATTR_MEALPLAN_ID,
    ATTR_NOTE_TEXT,
    ATTR_NOTE_TITLE,
    ATTR_RECIPE_ID,
    ATTR_RESULT_LIMIT,
    ATTR_SEARCH_TERMS,
    ATTR_START_DATE,
    ATTR_URL,
    DOMAIN,
)
from homeassistant.components.mealie.services import (
    SERVICE_DELETE_MEALPLAN,
    SERVICE_GET_MEALPLAN,
    SERVICE_GET_RECIPE,
    SERVICE_GET_RECIPES,
    SERVICE_GET_SHOPPING_LIST_ITEMS,
    SERVICE_IMPORT_RECIPE,
    SERVICE_SET_MEALPLAN,
    SERVICE_SET_RANDOM_MEALPLAN,
    SERVICE_UPDATE_MEALPLAN,
)
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_DATE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration

from tests.common import MockConfigEntry


async def test_service_mealplan(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the get_mealplan service."""

    await setup_integration(hass, mock_config_entry)

    freezer.move_to("2023-10-21T12:00:00-07:00")

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MEALPLAN,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert mock_mealie_client.get_mealplans.call_args_list[1][0] == (
        date(2023, 10, 21),
        date(2023, 10, 21),
    )
    assert response == snapshot

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_START_DATE: "2023-10-22",
            ATTR_END_DATE: "2023-10-25",
        },
        blocking=True,
        return_response=True,
    )
    assert response
    assert mock_mealie_client.get_mealplans.call_args_list[2][0] == (
        date(2023, 10, 22),
        date(2023, 10, 25),
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_START_DATE: "2023-10-19",
        },
        blocking=True,
        return_response=True,
    )
    assert response
    assert mock_mealie_client.get_mealplans.call_args_list[3][0] == (
        date(2023, 10, 19),
        date(2023, 10, 21),
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_END_DATE: "2023-10-22",
        },
        blocking=True,
        return_response=True,
    )
    assert response
    assert mock_mealie_client.get_mealplans.call_args_list[4][0] == (
        date(2023, 10, 21),
        date(2023, 10, 22),
    )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MEALPLAN,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_START_DATE: "2023-10-22",
                ATTR_END_DATE: "2023-10-19",
            },
            blocking=True,
            return_response=True,
        )


async def test_service_recipe(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the get_recipe service."""

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_RECIPE,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id, ATTR_RECIPE_ID: "recipe_id"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    "service_data",
    [
        # Default call
        {ATTR_CONFIG_ENTRY_ID: "mock_entry_id"},
        # With search terms and result limit
        {
            ATTR_CONFIG_ENTRY_ID: "mock_entry_id",
            ATTR_SEARCH_TERMS: "pasta",
            ATTR_RESULT_LIMIT: 5,
        },
    ],
)
async def test_service_get_recipes(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    service_data: dict,
) -> None:
    """Test the get_recipes service."""
    await setup_integration(hass, mock_config_entry)

    # Patch entry_id into service_data for each run
    service_data = {**service_data, ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id}

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_RECIPES,
        service_data,
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


async def test_service_import_recipe(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the import_recipe service."""

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_RECIPE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_URL: "http://example.com",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    mock_mealie_client.import_recipe.assert_called_with(
        "http://example.com", include_tags=False
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_RECIPE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_URL: "http://example.com",
            ATTR_INCLUDE_TAGS: True,
        },
        blocking=True,
        return_response=False,
    )
    mock_mealie_client.import_recipe.assert_called_with(
        "http://example.com", include_tags=True
    )


async def test_service_set_random_mealplan(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the set_random_mealplan service."""

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_RANDOM_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_DATE: "2023-10-21",
            ATTR_ENTRY_TYPE: "lunch",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    mock_mealie_client.random_mealplan.assert_called_with(
        date(2023, 10, 21), MealplanEntryType.LUNCH
    )

    mock_mealie_client.random_mealplan.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_RANDOM_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_DATE: "2023-10-21",
            ATTR_ENTRY_TYPE: "lunch",
        },
        blocking=True,
        return_response=False,
    )
    mock_mealie_client.random_mealplan.assert_called_with(
        date(2023, 10, 21), MealplanEntryType.LUNCH
    )


async def test_service_set_random_mealplan_invalid_entry_type(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the set_random_mealplan service with invalid entry types for version."""
    mock_mealie_client.get_about.return_value = About(version="v3.6.0")

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_RANDOM_MEALPLAN,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_DATE: "2023-10-21",
                ATTR_ENTRY_TYPE: "dessert",
            },
            blocking=True,
            return_response=True,
        )
    mock_mealie_client.random_mealplan.assert_not_called()


@pytest.mark.parametrize(
    ("payload", "kwargs"),
    [
        (
            {
                ATTR_RECIPE_ID: "recipe_id",
            },
            {"recipe_id": "recipe_id", "note_title": None, "note_text": None},
        ),
        (
            {
                ATTR_NOTE_TITLE: "Note Title",
                ATTR_NOTE_TEXT: "Note Text",
            },
            {"recipe_id": None, "note_title": "Note Title", "note_text": "Note Text"},
        ),
        (
            {
                ATTR_NOTE_TITLE: "Note Title",
            },
            {"recipe_id": None, "note_title": "Note Title", "note_text": None},
        ),
    ],
)
async def test_service_set_mealplan(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    payload: dict[str, str],
    kwargs: dict[str, str],
) -> None:
    """Test the set_mealplan service."""

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_DATE: "2023-10-21",
            ATTR_ENTRY_TYPE: "lunch",
        }
        | payload,
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    mock_mealie_client.set_mealplan.assert_called_with(
        date(2023, 10, 21), MealplanEntryType.LUNCH, **kwargs
    )

    mock_mealie_client.random_mealplan.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_DATE: "2023-10-21",
            ATTR_ENTRY_TYPE: "lunch",
        }
        | payload,
        blocking=True,
        return_response=False,
    )
    mock_mealie_client.set_mealplan.assert_called_with(
        date(2023, 10, 21), MealplanEntryType.LUNCH, **kwargs
    )


async def test_service_set_mealplan_invalid_entry_type(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the set_mealplan service with invalid entry types for version."""
    mock_mealie_client.get_about.return_value = About(version="v3.6.0")

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_MEALPLAN,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_DATE: "2023-10-21",
                ATTR_ENTRY_TYPE: "dessert",
                ATTR_NOTE_TITLE: "Note Title",
            },
            blocking=True,
            return_response=True,
        )
    mock_mealie_client.set_mealplan.assert_not_called()


async def test_service_delete_mealplan(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the delete_mealplan service."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_MEALPLAN_ID: "mealplan_id",
        },
        blocking=True,
    )
    mock_mealie_client.delete_mealplan.assert_called_with("mealplan_id")


async def test_service_delete_mealplan_not_found(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the delete_mealplan service with invalid mealplan ID."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.delete_mealplan.side_effect = MealieNotFoundError

    with pytest.raises(ServiceValidationError, match="Mealplan with ID"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_MEALPLAN,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_MEALPLAN_ID: "invalid_mealplan_id",
            },
            blocking=True,
        )
    mock_mealie_client.delete_mealplan.assert_called_once()


@pytest.mark.parametrize(
    ("payload", "kwargs"),
    [
        (
            {
                ATTR_RECIPE_ID: "recipe_id",
            },
            {"recipe_id": "recipe_id", "note_title": None, "note_text": None},
        ),
        (
            {
                ATTR_NOTE_TITLE: "Note Title",
                ATTR_NOTE_TEXT: "Note Text",
            },
            {"recipe_id": None, "note_title": "Note Title", "note_text": "Note Text"},
        ),
        (
            {
                ATTR_NOTE_TITLE: "Note Title",
            },
            {"recipe_id": None, "note_title": "Note Title", "note_text": None},
        ),
    ],
)
async def test_service_update_mealplan(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    payload: dict[str, str],
    kwargs: dict[str, str],
) -> None:
    """Test the update_mealplan service."""

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_MEALPLAN_ID: "mealplan_id",
            ATTR_DATE: "2023-10-21",
            ATTR_ENTRY_TYPE: "lunch",
        }
        | payload,
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    mock_mealie_client.update_mealplan.assert_called_with(
        "mealplan_id", date(2023, 10, 21), MealplanEntryType.LUNCH, **kwargs
    )

    mock_mealie_client.update_mealplan.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_MEALPLAN_ID: "mealplan_id",
            ATTR_DATE: "2023-10-21",
            ATTR_ENTRY_TYPE: "lunch",
        }
        | payload,
        blocking=True,
        return_response=False,
    )
    mock_mealie_client.update_mealplan.assert_called_with(
        "mealplan_id", date(2023, 10, 21), MealplanEntryType.LUNCH, **kwargs
    )


async def test_service_update_mealplan_invalid_entry_type(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the update_mealplan service with invalid entry types for version."""
    mock_mealie_client.get_about.return_value = About(version="v3.6.0")

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_MEALPLAN,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_MEALPLAN_ID: "mealplan_id",
                ATTR_DATE: "2023-10-21",
                ATTR_ENTRY_TYPE: "dessert",
                ATTR_NOTE_TITLE: "Note Title",
            },
            blocking=True,
            return_response=True,
        )
    mock_mealie_client.update_mealplan.assert_not_called()


async def test_service_update_mealplan_not_found(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the update_mealplan service with invalid mealplan ID."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.update_mealplan.side_effect = MealieNotFoundError

    with pytest.raises(ServiceValidationError, match="Mealplan with ID"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_MEALPLAN,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_MEALPLAN_ID: "invalid_mealplan_id",
                ATTR_DATE: "2023-10-21",
                ATTR_ENTRY_TYPE: "lunch",
                ATTR_RECIPE_ID: "recipe_id",
            },
            blocking=True,
            return_response=True,
        )
    mock_mealie_client.update_mealplan.assert_called_once()


async def test_service_get_shopping_list_items(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the get_shopping_list_items service."""

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_SHOPPING_LIST_ITEMS,
        target={"entity_id": "todo.mealie_supermarket"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


async def test_service_get_shopping_list_items_connection_error(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the get_shopping_list_items service with connection error."""

    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.get_shopping_items.side_effect = MealieConnectionError

    with pytest.raises(HomeAssistantError, match="Error connecting to Mealie instance"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SHOPPING_LIST_ITEMS,
            target={"entity_id": "todo.mealie_supermarket"},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    (
        "service",
        "payload",
        "function",
        "exception",
        "raised_exception",
        "message",
        "return_response",
    ),
    [
        (
            SERVICE_GET_MEALPLAN,
            {},
            "get_mealplans",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            True,
        ),
        (
            SERVICE_GET_RECIPE,
            {ATTR_RECIPE_ID: "recipe_id"},
            "get_recipe",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            True,
        ),
        (
            SERVICE_GET_RECIPE,
            {ATTR_RECIPE_ID: "recipe_id"},
            "get_recipe",
            MealieNotFoundError,
            ServiceValidationError,
            "Recipe with ID or slug `recipe_id` not found",
            True,
        ),
        (
            SERVICE_GET_RECIPES,
            {},
            "get_recipes",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            True,
        ),
        (
            SERVICE_GET_RECIPES,
            {ATTR_SEARCH_TERMS: "pasta"},
            "get_recipes",
            MealieNotFoundError,
            ServiceValidationError,
            "No recipes found matching your search",
            True,
        ),
        (
            SERVICE_IMPORT_RECIPE,
            {ATTR_URL: "http://example.com"},
            "import_recipe",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            True,
        ),
        (
            SERVICE_IMPORT_RECIPE,
            {ATTR_URL: "http://example.com"},
            "import_recipe",
            MealieValidationError,
            ServiceValidationError,
            "Mealie could not import the recipe from the URL",
            True,
        ),
        (
            SERVICE_SET_RANDOM_MEALPLAN,
            {ATTR_DATE: "2023-10-21", ATTR_ENTRY_TYPE: "lunch"},
            "random_mealplan",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            True,
        ),
        (
            SERVICE_SET_MEALPLAN,
            {
                ATTR_DATE: "2023-10-21",
                ATTR_ENTRY_TYPE: "lunch",
                ATTR_RECIPE_ID: "recipe_id",
            },
            "set_mealplan",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            True,
        ),
        (
            SERVICE_DELETE_MEALPLAN,
            {ATTR_MEALPLAN_ID: "mealplan_id"},
            "delete_mealplan",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            False,
        ),
        (
            SERVICE_UPDATE_MEALPLAN,
            {
                ATTR_MEALPLAN_ID: "mealplan_id",
                ATTR_DATE: "2023-10-21",
                ATTR_ENTRY_TYPE: "lunch",
                ATTR_RECIPE_ID: "recipe_id",
            },
            "update_mealplan",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            True,
        ),
    ],
)
async def test_services_connection_error(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    payload: dict[str, str],
    function: str,
    exception: Exception,
    raised_exception: type[Exception],
    message: str,
    return_response: bool,
) -> None:
    """Test a connection error in the services."""

    await setup_integration(hass, mock_config_entry)

    getattr(mock_mealie_client, function).side_effect = exception

    with pytest.raises(raised_exception, match=message):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id} | payload,
            blocking=True,
            return_response=return_response,
        )


@pytest.mark.parametrize(
    ("service", "payload", "return_response"),
    [
        (SERVICE_GET_MEALPLAN, {}, True),
        (SERVICE_GET_RECIPE, {ATTR_RECIPE_ID: "recipe_id"}, True),
        (SERVICE_GET_RECIPES, {}, True),
        (
            SERVICE_GET_RECIPES,
            {ATTR_SEARCH_TERMS: "pasta", ATTR_RESULT_LIMIT: 5},
            True,
        ),
        (SERVICE_IMPORT_RECIPE, {ATTR_URL: "http://example.com"}, True),
        (
            SERVICE_SET_RANDOM_MEALPLAN,
            {ATTR_DATE: "2023-10-21", ATTR_ENTRY_TYPE: "lunch"},
            True,
        ),
        (
            SERVICE_SET_MEALPLAN,
            {
                ATTR_DATE: "2023-10-21",
                ATTR_ENTRY_TYPE: "lunch",
                ATTR_RECIPE_ID: "recipe_id",
            },
            True,
        ),
        (SERVICE_DELETE_MEALPLAN, {ATTR_MEALPLAN_ID: "mealplan_id"}, False),
        (
            SERVICE_UPDATE_MEALPLAN,
            {
                ATTR_MEALPLAN_ID: "mealplan_id",
                ATTR_DATE: "2023-10-21",
                ATTR_ENTRY_TYPE: "lunch",
                ATTR_RECIPE_ID: "recipe_id",
            },
            True,
        ),
    ],
)
async def test_service_entry_availability(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    payload: dict[str, str],
    return_response: bool,
) -> None:
    """Test the services without valid entry."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry2 = MockConfigEntry(domain=DOMAIN)
    mock_config_entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry2.entry_id} | payload,
            blocking=True,
            return_response=return_response,
        )
    assert err.value.translation_key == "service_config_entry_not_loaded"

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: "bad-config_id"} | payload,
            blocking=True,
            return_response=return_response,
        )
    assert err.value.translation_key == "service_config_entry_not_found"
