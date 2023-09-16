"""Common fixtures for the NEW_NAME tests."""
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.local_todo import LocalTodoListStore
from homeassistant.components.local_todo.const import CONF_TODO_LIST_NAME, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TODO_NAME = "My Tasks"
FRIENDLY_NAME = "My tasks"
TEST_ENTITY = "todo.my_tasks"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.local_todo.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


class FakeStore(LocalTodoListStore):
    """Mock storage implementation."""

    def __init__(self, hass: HomeAssistant, path: Path, ics_content: str) -> None:
        """Initialize FakeStore."""
        super().__init__(hass, path)
        self._content = ics_content

    def _load(self) -> str:
        """Read from todo storage."""
        return self._content

    def _store(self, ics_content: str) -> None:
        """Persist the todo storage."""
        self._content = ics_content


@pytest.fixture(name="ics_content", autouse=True)
def mock_ics_content() -> str:
    """Fixture to allow tests to set initial ics content for the todo store."""
    return ""


@pytest.fixture(name="store", autouse=True)
def mock_store(ics_content: str) -> Generator[None, None, None]:
    """Test cleanup, remove any media storage persisted during the test."""

    stores: dict[Path, FakeStore] = {}

    def new_store(hass: HomeAssistant, path: Path) -> FakeStore:
        if path not in stores:
            stores[path] = FakeStore(hass, path, ics_content)
        return stores[path]

    with patch("homeassistant.components.local_todo.LocalTodoListStore", new=new_store):
        yield


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    return MockConfigEntry(domain=DOMAIN, data={CONF_TODO_LIST_NAME: TODO_NAME})


@pytest.fixture(name="setup_integration")
async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the integration."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
