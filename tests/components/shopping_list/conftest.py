"""Shopping list test helpers."""

from collections.abc import Generator
from contextlib import suppress
import os

import pytest

from homeassistant.components.shopping_list import intent as sl_intent
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def wipe_shopping_list_store(hass: HomeAssistant) -> Generator[None]:
    """Wipe shopping list store after test."""
    try:
        yield
    finally:
        with suppress(FileNotFoundError):
            os.remove(hass.config.path(".shopping_list.json"))


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
