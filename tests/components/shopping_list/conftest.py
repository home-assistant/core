"""Shopping list test helpers."""
from asynctest import patch
import pytest

from homeassistant.components.shopping_list import intent as sl_intent

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_shopping_list_io():
    """Stub out the persistence."""
    with patch("homeassistant.components.shopping_list.ShoppingData.save"), patch(
        "homeassistant.components.shopping_list.ShoppingData.async_load"
    ):
        yield


@pytest.fixture
async def sl_setup(hass):
    """Set up the shopping list."""

    entry = MockConfigEntry(domain="shopping_list")
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    await sl_intent.async_setup_intents(hass)
