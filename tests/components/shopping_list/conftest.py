"""Shopping list test helpers."""
from unittest.mock import patch

import pytest

from homeassistant.components.shopping_list import intent as sl_intent
from homeassistant.setup import async_setup_component


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
    assert await async_setup_component(hass, "shopping_list", {})
    await sl_intent.async_setup_intents(hass)
