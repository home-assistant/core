"""Tests for the Mealie services."""

from dataclasses import replace
from datetime import date
from unittest.mock import AsyncMock

from aiomealie import (
    About,
    IngredientConfidence,
    MealieConnectionError,
    MealieNotFoundError,
    MealieValidationError,
    MealplanEntryType,
    MutateShoppingItem,
    ParsedIngredient,
    RegisteredParser,
)
from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, load_fixture
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mealie.const import DOMAIN
from homeassistant.components.mealie.services import (
    MealieService,
    MealieServiceArgument,
)
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration


@pytest.mark.parametrize(
    ("data", "item"),
    [
        pytest.param(
            {MealieServiceArgument.FOOD_ID: "09322430-d24c-4b1a-abb6-22b6ed3a88f5"},
            MutateShoppingItem(
                food_id="09322430-d24c-4b1a-abb6-22b6ed3a88f5",
                quantity=0.0,
                is_food=True,
            ),
            id="food-only",
        ),
        pytest.param(
            {MealieServiceArgument.NOTE: "Kitchen roll"},
            MutateShoppingItem(note="Kitchen roll", quantity=0.0, is_food=False),
            id="note-only",
        ),
        pytest.param(
            {
                MealieServiceArgument.FOOD_ID: "",
                MealieServiceArgument.NOTE: "Kitchen roll",
            },
            MutateShoppingItem(note="Kitchen roll", quantity=0.0, is_food=False),
            id="empty-food-id",
        ),
        pytest.param(
            {
                MealieServiceArgument.FOOD_ID: "09322430-d24c-4b1a-abb6-22b6ed3a88f5",
                MealieServiceArgument.NOTE: "Diced",
                MealieServiceArgument.UNIT_ID: "7bf539d4-fc78-48bc-b48e-c35ccccec34a",
                MealieServiceArgument.QUANTITY: 1.5,
            },
            MutateShoppingItem(
                food_id="09322430-d24c-4b1a-abb6-22b6ed3a88f5",
                note="Diced",
                unit_id="7bf539d4-fc78-48bc-b48e-c35ccccec34a",
                quantity=1.5,
                is_food=True,
            ),
            id="all-fields",
        ),
        pytest.param(
            {MealieServiceArgument.NOTE: "Apples", MealieServiceArgument.QUANTITY: 0},
            MutateShoppingItem(note="Apples", quantity=0.0, is_food=False),
            id="zero-quantity",
        ),
    ],
)
@pytest.mark.parametrize(
    ("item_count", "position"),
    [
        pytest.param(0, 0, id="empty-list"),
        pytest.param(4, 1, id="populated-list"),
    ],
)
async def test_service_add_ingredient(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    data: dict[str, str | float],
    item: MutateShoppingItem,
    item_count: int,
    position: int,
) -> None:
    """Test adding ingredients directly to the targeted shopping list."""
    mock_mealie_client.get_shopping_items.return_value.items = (
        mock_mealie_client.get_shopping_items.return_value.items[:item_count]
    )
    await setup_integration(hass, mock_config_entry)
    mock_mealie_client.get_shopping_lists.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        MealieService.ADD_INGREDIENT,
        data,
        target={ATTR_ENTITY_ID: "todo.mealie_special_groceries"},
        blocking=True,
    )

    mock_mealie_client.add_shopping_item.assert_awaited_once_with(
        replace(
            item,
            list_id="f8438635-8211-4be8-80d0-0aa42e37a5f2",
            position=position,
        )
    )
    mock_mealie_client.parse_ingredient.assert_not_awaited()
    mock_mealie_client.get_shopping_lists.assert_awaited_once()


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({MealieServiceArgument.FOOD_ID: 1}, id="invalid-food-id"),
        pytest.param({MealieServiceArgument.NOTE: None}, id="invalid-note"),
        pytest.param(
            {MealieServiceArgument.NOTE: "Apples", MealieServiceArgument.QUANTITY: -1},
            id="negative-quantity",
        ),
        pytest.param(
            {
                MealieServiceArgument.NOTE: "Apples",
                MealieServiceArgument.QUANTITY: "many",
            },
            id="invalid-quantity",
        ),
        pytest.param(
            {MealieServiceArgument.NOTE: "Apples", MealieServiceArgument.UNIT_ID: 1},
            id="invalid-unit-id",
        ),
        pytest.param(
            {
                MealieServiceArgument.NOTE: "Apples",
                "ingredient_label_id": "1a1b8adf-277b-4db1-bdcc-12dbec75fd8a",
            },
            id="unsupported-ingredient-label-id",
        ),
    ],
)
async def test_service_add_ingredient_invalid(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    data: dict[str, str | int | None],
) -> None:
    """Test ingredient field validation before calling Mealie."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            MealieService.ADD_INGREDIENT,
            data,
            target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
            blocking=True,
        )

    mock_mealie_client.add_shopping_item.assert_not_awaited()


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({}, id="missing-food-and-note"),
        pytest.param({MealieServiceArgument.QUANTITY: 0}, id="quantity-only"),
        pytest.param({MealieServiceArgument.NOTE: ""}, id="empty-note"),
        pytest.param({MealieServiceArgument.FOOD_ID: ""}, id="empty-food-id"),
        pytest.param(
            {MealieServiceArgument.FOOD_ID: "", MealieServiceArgument.NOTE: ""},
            id="empty-food-and-note",
        ),
    ],
)
async def test_service_add_ingredient_requires_food_or_note(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    data: dict[str, str | int],
) -> None:
    """Test missing ingredient details produce a translated validation error."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        ServiceValidationError,
        match="Provide a food ID or a note to add an ingredient",
    ):
        await hass.services.async_call(
            DOMAIN,
            MealieService.ADD_INGREDIENT,
            data,
            target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
            blocking=True,
        )

    mock_mealie_client.add_shopping_item.assert_not_awaited()


async def test_service_add_ingredient_error(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an ingredient API failure still refreshes the shopping list."""
    await setup_integration(hass, mock_config_entry)
    mock_mealie_client.add_shopping_item.side_effect = MealieConnectionError
    mock_mealie_client.get_shopping_lists.reset_mock()

    with pytest.raises(
        HomeAssistantError, match="An error occurred adding an item to Supermarket"
    ):
        await hass.services.async_call(
            DOMAIN,
            MealieService.ADD_INGREDIENT,
            {MealieServiceArgument.NOTE: "Apples"},
            target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
            blocking=True,
        )

    mock_mealie_client.get_shopping_lists.assert_awaited_once()


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
        MealieService.GET_MEALPLAN,
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
        MealieService.GET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.START_DATE: "2023-10-22",
            MealieServiceArgument.END_DATE: "2023-10-25",
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
        MealieService.GET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.START_DATE: "2023-10-19",
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
        MealieService.GET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.END_DATE: "2023-10-22",
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
            MealieService.GET_MEALPLAN,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                MealieServiceArgument.START_DATE: "2023-10-22",
                MealieServiceArgument.END_DATE: "2023-10-19",
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
        MealieService.GET_RECIPE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.RECIPE_ID: "recipe_id",
        },
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
            MealieServiceArgument.SEARCH_TERMS: "pasta",
            MealieServiceArgument.RESULT_LIMIT: 5,
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
        MealieService.GET_RECIPES,
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
        MealieService.IMPORT_RECIPE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.URL: "http://example.com",
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
        MealieService.IMPORT_RECIPE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.URL: "http://example.com",
            MealieServiceArgument.INCLUDE_TAGS: True,
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
        MealieService.SET_RANDOM_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.DATE: "2023-10-21",
            MealieServiceArgument.ENTRY_TYPE: "lunch",
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
        MealieService.SET_RANDOM_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.DATE: "2023-10-21",
            MealieServiceArgument.ENTRY_TYPE: "lunch",
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
            MealieService.SET_RANDOM_MEALPLAN,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                MealieServiceArgument.DATE: "2023-10-21",
                MealieServiceArgument.ENTRY_TYPE: "dessert",
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
                MealieServiceArgument.RECIPE_ID: "recipe_id",
            },
            {"recipe_id": "recipe_id", "note_title": None, "note_text": None},
        ),
        (
            {
                MealieServiceArgument.NOTE_TITLE: "Note Title",
                MealieServiceArgument.NOTE_TEXT: "Note Text",
            },
            {"recipe_id": None, "note_title": "Note Title", "note_text": "Note Text"},
        ),
        (
            {
                MealieServiceArgument.NOTE_TITLE: "Note Title",
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
        MealieService.SET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.DATE: "2023-10-21",
            MealieServiceArgument.ENTRY_TYPE: "lunch",
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
        MealieService.SET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.DATE: "2023-10-21",
            MealieServiceArgument.ENTRY_TYPE: "lunch",
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
            MealieService.SET_MEALPLAN,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                MealieServiceArgument.DATE: "2023-10-21",
                MealieServiceArgument.ENTRY_TYPE: "dessert",
                MealieServiceArgument.NOTE_TITLE: "Note Title",
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
        MealieService.DELETE_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.MEALPLAN_ID: "16",
        },
        blocking=True,
    )
    mock_mealie_client.delete_mealplan.assert_called_with(16)

    await hass.services.async_call(
        DOMAIN,
        MealieService.DELETE_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.MEALPLAN_ID: 16,
        },
        blocking=True,
    )
    mock_mealie_client.delete_mealplan.assert_called_with(16)


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
            MealieService.DELETE_MEALPLAN,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                MealieServiceArgument.MEALPLAN_ID: "16",
            },
            blocking=True,
        )
    mock_mealie_client.delete_mealplan.assert_called_once()


@pytest.mark.parametrize(
    ("payload", "kwargs"),
    [
        (
            {
                MealieServiceArgument.RECIPE_ID: "recipe_id",
            },
            {"recipe_id": "recipe_id", "note_title": None, "note_text": None},
        ),
        (
            {
                MealieServiceArgument.NOTE_TITLE: "Note Title",
                MealieServiceArgument.NOTE_TEXT: "Note Text",
            },
            {"recipe_id": None, "note_title": "Note Title", "note_text": "Note Text"},
        ),
        (
            {
                MealieServiceArgument.NOTE_TITLE: "Note Title",
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
        MealieService.UPDATE_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.MEALPLAN_ID: "16",
            MealieServiceArgument.DATE: "2023-10-21",
            MealieServiceArgument.ENTRY_TYPE: "lunch",
        }
        | payload,
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    mock_mealie_client.update_mealplan.assert_called_with(
        16, date(2023, 10, 21), MealplanEntryType.LUNCH, **kwargs
    )

    mock_mealie_client.update_mealplan.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        MealieService.UPDATE_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.MEALPLAN_ID: "16",
            MealieServiceArgument.DATE: "2023-10-21",
            MealieServiceArgument.ENTRY_TYPE: "lunch",
        }
        | payload,
        blocking=True,
        return_response=False,
    )
    mock_mealie_client.update_mealplan.assert_called_with(
        16, date(2023, 10, 21), MealplanEntryType.LUNCH, **kwargs
    )

    mock_mealie_client.update_mealplan.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        MealieService.UPDATE_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.MEALPLAN_ID: 16,
            MealieServiceArgument.DATE: "2023-10-21",
            MealieServiceArgument.ENTRY_TYPE: "lunch",
        }
        | payload,
        blocking=True,
        return_response=False,
    )
    mock_mealie_client.update_mealplan.assert_called_with(
        16, date(2023, 10, 21), MealplanEntryType.LUNCH, **kwargs
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
            MealieService.UPDATE_MEALPLAN,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                MealieServiceArgument.MEALPLAN_ID: "16",
                MealieServiceArgument.DATE: "2023-10-21",
                MealieServiceArgument.ENTRY_TYPE: "dessert",
                MealieServiceArgument.NOTE_TITLE: "Note Title",
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
            MealieService.UPDATE_MEALPLAN,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                MealieServiceArgument.MEALPLAN_ID: "16",
                MealieServiceArgument.DATE: "2023-10-21",
                MealieServiceArgument.ENTRY_TYPE: "lunch",
                MealieServiceArgument.RECIPE_ID: "recipe_id",
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
        MealieService.GET_SHOPPING_LIST_ITEMS,
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
            MealieService.GET_SHOPPING_LIST_ITEMS,
            target={"entity_id": "todo.mealie_supermarket"},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    "confidence",
    [
        pytest.param(IngredientConfidence(average=1.0), id="high-confidence"),
        pytest.param(IngredientConfidence(average=0.98), id="threshold-confidence"),
        pytest.param(IngredientConfidence(average=0.979), id="low-confidence"),
        pytest.param(IngredientConfidence(average=0.0), id="zero-confidence"),
    ],
)
async def test_service_parse_ingredient(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    confidence: IngredientConfidence,
) -> None:
    """Test ingredient parsing and confidence in the service response."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.parse_ingredient.return_value.confidence = confidence

    response = await hass.services.async_call(
        DOMAIN,
        MealieService.PARSE_INGREDIENT,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            MealieServiceArgument.INGREDIENT: "1 can acorn squash",
        },
        blocking=True,
        return_response=True,
    )

    mock_mealie_client.parse_ingredient.assert_awaited_once_with(
        "1 can acorn squash", RegisteredParser.NLP
    )
    assert response == snapshot


@pytest.mark.parametrize(
    "result",
    [
        pytest.param(None, id="missing-result"),
        pytest.param(
            replace(
                ParsedIngredient.from_json(
                    load_fixture("parse_ingredient.json", DOMAIN)
                ),
                confidence=None,
            ),
            id="missing-confidence",
        ),
    ],
)
async def test_service_get_ingredient_parse_failure(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    result: ParsedIngredient | None,
) -> None:
    """Test parsing failures raise a translated service error."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.parse_ingredient.return_value = result

    with pytest.raises(
        ServiceValidationError, match="Mealie could not parse the ingredient"
    ) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            MealieService.PARSE_INGREDIENT,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                MealieServiceArgument.INGREDIENT: "1 can acorn squash",
            },
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "could_not_parse_ingredient"
    mock_mealie_client.parse_ingredient.assert_awaited_once_with(
        "1 can acorn squash", RegisteredParser.NLP
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
        pytest.param(
            MealieService.PARSE_INGREDIENT,
            {MealieServiceArgument.INGREDIENT: "1 can acorn squash"},
            "parse_ingredient",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            True,
            id="parse-ingredient-connection-error",
        ),
        (
            MealieService.GET_MEALPLAN,
            {},
            "get_mealplans",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            True,
        ),
        (
            MealieService.GET_RECIPE,
            {MealieServiceArgument.RECIPE_ID: "recipe_id"},
            "get_recipe",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            True,
        ),
        (
            MealieService.GET_RECIPE,
            {MealieServiceArgument.RECIPE_ID: "recipe_id"},
            "get_recipe",
            MealieNotFoundError,
            ServiceValidationError,
            "Recipe with ID or slug `recipe_id` not found",
            True,
        ),
        (
            MealieService.GET_RECIPES,
            {},
            "get_recipes",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            True,
        ),
        (
            MealieService.GET_RECIPES,
            {MealieServiceArgument.SEARCH_TERMS: "pasta"},
            "get_recipes",
            MealieNotFoundError,
            ServiceValidationError,
            "No recipes found matching your search",
            True,
        ),
        (
            MealieService.IMPORT_RECIPE,
            {MealieServiceArgument.URL: "http://example.com"},
            "import_recipe",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            True,
        ),
        (
            MealieService.IMPORT_RECIPE,
            {MealieServiceArgument.URL: "http://example.com"},
            "import_recipe",
            MealieValidationError,
            ServiceValidationError,
            "Mealie could not import the recipe from the URL",
            True,
        ),
        (
            MealieService.SET_RANDOM_MEALPLAN,
            {
                MealieServiceArgument.DATE: "2023-10-21",
                MealieServiceArgument.ENTRY_TYPE: "lunch",
            },
            "random_mealplan",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            True,
        ),
        (
            MealieService.SET_MEALPLAN,
            {
                MealieServiceArgument.DATE: "2023-10-21",
                MealieServiceArgument.ENTRY_TYPE: "lunch",
                MealieServiceArgument.RECIPE_ID: "recipe_id",
            },
            "set_mealplan",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            True,
        ),
        (
            MealieService.DELETE_MEALPLAN,
            {MealieServiceArgument.MEALPLAN_ID: "16"},
            "delete_mealplan",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
            False,
        ),
        (
            MealieService.UPDATE_MEALPLAN,
            {
                MealieServiceArgument.MEALPLAN_ID: "16",
                MealieServiceArgument.DATE: "2023-10-21",
                MealieServiceArgument.ENTRY_TYPE: "lunch",
                MealieServiceArgument.RECIPE_ID: "recipe_id",
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
        pytest.param(
            MealieService.PARSE_INGREDIENT,
            {MealieServiceArgument.INGREDIENT: "1 can acorn squash"},
            True,
            id="parse-ingredient",
        ),
        (MealieService.GET_MEALPLAN, {}, True),
        (
            MealieService.GET_RECIPE,
            {MealieServiceArgument.RECIPE_ID: "recipe_id"},
            True,
        ),
        (MealieService.GET_RECIPES, {}, True),
        (
            MealieService.GET_RECIPES,
            {
                MealieServiceArgument.SEARCH_TERMS: "pasta",
                MealieServiceArgument.RESULT_LIMIT: 5,
            },
            True,
        ),
        (
            MealieService.IMPORT_RECIPE,
            {MealieServiceArgument.URL: "http://example.com"},
            True,
        ),
        (
            MealieService.SET_RANDOM_MEALPLAN,
            {
                MealieServiceArgument.DATE: "2023-10-21",
                MealieServiceArgument.ENTRY_TYPE: "lunch",
            },
            True,
        ),
        (
            MealieService.SET_MEALPLAN,
            {
                MealieServiceArgument.DATE: "2023-10-21",
                MealieServiceArgument.ENTRY_TYPE: "lunch",
                MealieServiceArgument.RECIPE_ID: "recipe_id",
            },
            True,
        ),
        (
            MealieService.DELETE_MEALPLAN,
            {MealieServiceArgument.MEALPLAN_ID: "16"},
            False,
        ),
        (
            MealieService.UPDATE_MEALPLAN,
            {
                MealieServiceArgument.MEALPLAN_ID: "16",
                MealieServiceArgument.DATE: "2023-10-21",
                MealieServiceArgument.ENTRY_TYPE: "lunch",
                MealieServiceArgument.RECIPE_ID: "recipe_id",
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
