"""Tests for the todo intents."""

from collections.abc import Generator
import logging

import pytest

from homeassistant.components import conversation
from homeassistant.components.todo import (
    ATTR_ITEM,
    DOMAIN,
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    intent as todo_intent,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow
from homeassistant.const import ATTR_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    async_mock_service,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
from tests.typing import WebSocketGenerator

_LOGGER = logging.getLogger(__name__)

TEST_DOMAIN = "test"


class MockFlow(ConfigFlow):
    """Test flow."""


class MockTodoListEntity(TodoListEntity):
    """Mock TodoListEntity for testing."""

    def __init__(self, items: list[TodoItem] | None = None) -> None:
        """Initialize mock entity."""
        self._attr_todo_items = items or []
        self._attr_supported_features = TodoListEntity.supported_features

    @property
    def items(self) -> list[TodoItem]:
        """Return the items in the To-do list."""
        return self._attr_todo_items

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        self._attr_todo_items.append(item)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item in the To-do list."""
        for index, existing_item in enumerate(self._attr_todo_items):
            if existing_item.uid == item.uid:
                self._attr_todo_items[index] = item
                break

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete items from the To-do list."""
        self._attr_todo_items = [item for item in self.items if item.uid not in uids]


async def create_mock_platform(
    hass: HomeAssistant,
    entities: list[TodoListEntity],
) -> MockConfigEntry:
    """Create a todo platform with the specified entities."""

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test event platform via config entry."""
        async_add_entities(entities)

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


@pytest.fixture(autouse=True)
async def setup_intents(hass: HomeAssistant) -> None:
    """Set up the intents."""
    assert await async_setup_component(hass, "homeassistant", {})
    await todo_intent.async_setup_intents(hass)


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


@pytest.fixture(autouse=True)
def mock_setup_integration(hass: HomeAssistant) -> None:
    """Fixture to set up a mock integration."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> bool:
        await hass.config_entries.async_unload_platforms(config_entry, [Platform.TODO])
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
            async_unload_entry=async_unload_entry_init,
        ),
    )


async def test_remove_item_intent(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test removing items from lists using an intent."""
    entity1 = MockTodoListEntity(
        [
            TodoItem(summary="beer", uid="1", status=TodoItemStatus.NEEDS_ACTION),
            TodoItem(summary="wine", uid="2", status=TodoItemStatus.NEEDS_ACTION),
        ]
    )
    entity1._attr_name = "List 1"
    entity1.entity_id = "todo.list_1"

    entity2 = MockTodoListEntity(
        [TodoItem(summary="cheese", uid="3", status=TodoItemStatus.NEEDS_ACTION)]
    )
    entity2._attr_name = "List 2"
    entity2.entity_id = "todo.list_2"

    # Add entities to hass
    config_entry = await create_mock_platform(hass, [entity1, entity2])
    assert config_entry.state is ConfigEntryState.LOADED

    async_mock_service(hass, DOMAIN, todo_intent.INTENT_LIST_REMOVE_ITEM)

    assert len(entity1.items) == 2
    assert len(entity2.items) == 1

    # Remove from first list
    response = await intent.async_handle(
        hass,
        DOMAIN,
        todo_intent.INTENT_LIST_REMOVE_ITEM,
        {ATTR_ITEM: {"value": "beer"}, ATTR_NAME: {"value": "list 1"}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type == intent.IntentResponseType.ACTION_DONE

    assert len(entity1.items) == 1
    assert entity1.items[0].summary == "wine"
    assert len(entity2.items) == 1

    # Remove from second list
    response = await intent.async_handle(
        hass,
        "test",
        todo_intent.INTENT_LIST_REMOVE_ITEM,
        {ATTR_ITEM: {"value": "cheese"}, ATTR_NAME: {"value": "List 2"}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type == intent.IntentResponseType.ACTION_DONE

    assert len(entity1.items) == 1
    assert len(entity2.items) == 0

    # Try to remove non-existent item
    with pytest.raises(intent.IntentHandleError):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_REMOVE_ITEM,
            {ATTR_ITEM: {"value": "bread"}, ATTR_NAME: {"value": "list 1"}},
            assistant=conversation.DOMAIN,
        )

    # Try to remove from non-existent list
    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            todo_intent.INTENT_LIST_REMOVE_ITEM,
            {
                ATTR_ITEM: {"value": "wine"},
                ATTR_NAME: {"value": "This list does not exist"},
            },
            assistant=conversation.DOMAIN,
        )
