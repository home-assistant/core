"""Shopping list test helpers."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.components.shopping_list import PERSISTENCE, intent as sl_intent
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def shopping_list_tmp_path(tmp_path: Path, hass: HomeAssistant) -> Generator[None]:
    """Use a unique temp directory for shopping list storage per test."""
    orig_path = hass.config.path

    def _mock_path(*args: str) -> str:
        if args == (PERSISTENCE,):
            return str(tmp_path / PERSISTENCE)
        return orig_path(*args)

    with patch.object(hass.config, "path", _mock_path):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Config Entry fixture."""
    return MockConfigEntry(domain="shopping_list")


@pytest.fixture
async def sl_setup(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the shopping list."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await sl_intent.async_setup_intents(hass)
