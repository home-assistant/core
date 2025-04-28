"""Fixtures for the todo component tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.todo import (
    DOMAIN,
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import TEST_DOMAIN, MockFlow, MockTodoListEntity

from tests.common import MockModule, mock_config_flow, mock_integration, mock_platform


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


@pytest.fixture(autouse=True)
async def set_time_zone(hass: HomeAssistant) -> None:
    """Set the time zone for the tests that keesp UTC-6 all year round."""
    await hass.config.async_set_time_zone("America/Regina")


@pytest.fixture(name="test_entity_items")
def mock_test_entity_items() -> list[TodoItem]:
    """Fixture that creates the items returned by the test entity."""
    return [
        TodoItem(summary="Item #1", uid="1", status=TodoItemStatus.NEEDS_ACTION),
        TodoItem(summary="Item #2", uid="2", status=TodoItemStatus.COMPLETED),
    ]


@pytest.fixture(name="test_entity")
def mock_test_entity(test_entity_items: list[TodoItem]) -> TodoListEntity:
    """Fixture that creates a test TodoList entity with mock service calls."""
    entity1 = MockTodoListEntity(test_entity_items)
    entity1.entity_id = "todo.entity1"
    entity1._attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
    )
    entity1.async_create_todo_item = AsyncMock(wraps=entity1.async_create_todo_item)
    entity1.async_update_todo_item = AsyncMock()
    entity1.async_delete_todo_items = AsyncMock(wraps=entity1.async_delete_todo_items)
    entity1.async_move_todo_item = AsyncMock()
    return entity1
