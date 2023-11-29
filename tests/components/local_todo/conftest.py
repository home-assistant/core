"""Common fixtures for the local_todo tests."""
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.local_todo import LocalTodoListStore
from homeassistant.components.local_todo.const import (
    CONF_STORAGE_KEY,
    CONF_TODO_LIST_NAME,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TODO_NAME = "My Tasks"
FRIENDLY_NAME = "My tasks"
STORAGE_KEY = "my_tasks"
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

    def __init__(
        self,
        hass: HomeAssistant,
        path: Path,
        ics_content: str | None,
        read_side_effect: Any | None = None,
    ) -> None:
        """Initialize FakeStore."""
        mock_path = self._mock_path = Mock()
        mock_path.exists = self._mock_exists
        mock_path.read_text = Mock()
        mock_path.read_text.return_value = ics_content
        mock_path.read_text.side_effect = read_side_effect
        mock_path.write_text = self._mock_write_text

        super().__init__(hass, mock_path)

    def _mock_exists(self) -> bool:
        return self._mock_path.read_text.return_value is not None

    def _mock_write_text(self, content: str) -> None:
        self._mock_path.read_text.return_value = content


@pytest.fixture(name="ics_content")
def mock_ics_content() -> str | None:
    """Fixture to set .ics file content."""
    return ""


@pytest.fixture(name="store_read_side_effect")
def mock_store_read_side_effect() -> Any | None:
    """Fixture to raise errors from the FakeStore."""
    return None


@pytest.fixture(name="store", autouse=True)
def mock_store(
    ics_content: str, store_read_side_effect: Any | None
) -> Generator[None, None, None]:
    """Fixture that sets up a fake local storage object."""

    stores: dict[Path, FakeStore] = {}

    def new_store(hass: HomeAssistant, path: Path) -> FakeStore:
        if path not in stores:
            stores[path] = FakeStore(hass, path, ics_content, store_read_side_effect)
        return stores[path]

    with patch("homeassistant.components.local_todo.LocalTodoListStore", new=new_store):
        yield


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STORAGE_KEY: STORAGE_KEY, CONF_TODO_LIST_NAME: TODO_NAME},
    )


@pytest.fixture(name="setup_integration")
async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
