"""Tests for the To-do integration."""

from homeassistant.components.todo import DOMAIN, TodoItem, TodoListEntity
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from tests.common import MockConfigEntry, MockPlatform, mock_platform

TEST_DOMAIN = "test"


class MockFlow(ConfigFlow):
    """Test flow."""


class MockTodoListEntity(TodoListEntity):
    """Test todo list entity."""

    def __init__(self, items: list[TodoItem] | None = None) -> None:
        """Initialize entity."""
        self._attr_todo_items = items or []

    @property
    def items(self) -> list[TodoItem]:
        """Return the items in the To-do list."""
        return self._attr_todo_items

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        self._attr_todo_items.append(item)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete an item in the To-do list."""
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
