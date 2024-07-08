"""Tests for the Mealie todo."""

from http import HTTPStatus
from unittest.mock import AsyncMock, patch

from aiomealie import MutateShoppingItem, ShoppingItem
import pytest
from requests.exceptions import HTTPError
from requests.models import Response
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import make_shopping_item

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.TODO]


@pytest.fixture(name="api")
def mock_api(tasks: list[ShoppingItem]) -> AsyncMock:
    """Mock the api state."""
    api = AsyncMock()
    api.get_shopping_items.return_value = tasks
    return api


@pytest.fixture(name="mealie_api_status")
def mock_api_status() -> HTTPStatus | None:
    """Fixture to inject an http status error."""
    return None


@pytest.fixture(name="tasks")
def mock_tasks() -> list[MutateShoppingItem]:
    """Mock a mealie shopping item instance."""
    return [make_shopping_item()]


@pytest.fixture(autouse=True)
def mock_api_side_effect(
    api: AsyncMock, mealie_api_status: HTTPStatus | None
) -> MockConfigEntry:
    """Mock todoist configuration."""
    if mealie_api_status:
        response = Response()
        response.status_code = mealie_api_status
        api.get_tasks.side_effect = HTTPError(response=response)


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test todo entities."""
    with patch("homeassistant.components.mealie.PLATFORMS", [Platform.TODO]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_get_todo_list_items(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for getting a To-do list."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("todo.mealie_supermarket")
    assert state
    assert state.state == "3"


async def test_get_non_existant_todo_list_items(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for getting a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.get_shopping_items.return_value = {
        frozenset(
            {
                "quantity": 1.0,
                "unit": None,
                "food": None,
                "note": "Soda",
                "isFood": False,
                "disableAmount": True,
                "display": "Soda",
                "shoppingListId": "27edbaab-2ec6-441f-8490-0283ea77585f",
                "checked": False,
                "position": 0,
                "foodId": None,
                "labelId": None,
                "unitId": None,
                "extras": {},
                "id": "f45430f7-3edf-45a9-a50f-73bb375090be",
                "label": None,
                "recipeReferences": [],
                "createdAt": "2024-06-25T10:45:03.362623",
                "updateAt": "2024-06-25T11:57:22.412650",
            }
        )
    }

    await hass.services.async_call(
        Platform.TODO,
        "get_items",
        {},
        target={"entity_id": "todo.mealie_supermarket"},
        blocking=True,
        return_response=True,
    )

    state = hass.states.get("todo.not_a_list")
    assert state is None


async def test_add_todo_list_item(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for adding a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.add_shopping_item = AsyncMock()

    await hass.services.async_call(
        Platform.TODO,
        "add_item",
        {"item": "Soda"},
        target={"entity_id": "todo.mealie_supermarket"},
        blocking=True,
    )


async def test_update_todo_list_item(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for adding a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.update_shopping_item = AsyncMock()

    await hass.services.async_call(
        Platform.TODO,
        "update_item",
        {"item": "aubergine", "rename": "Eggplant", "status": "completed"},
        target={"entity_id": "todo.mealie_supermarket"},
        blocking=True,
    )


async def test_delete_todo_list_item(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for deleting a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.delete_shopping_item = AsyncMock()

    await hass.services.async_call(
        Platform.TODO,
        "remove_item",
        {"item": "aubergine"},
        target={"entity_id": "todo.mealie_supermarket"},
        blocking=True,
    )
