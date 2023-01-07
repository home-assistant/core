"""Shopping list test helpers."""
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant

from homeassistant.components.shopping_list import intent as sl_intent
from homeassistant.components.shopping_list.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_shopping_list_io():
    """Stub out the persistence."""
    with patch("homeassistant.components.shopping_list.ShoppingData.save"), patch(
        "homeassistant.components.shopping_list.ShoppingData.async_load"
    ):
        yield


@pytest.fixture
async def sl_setup(hass: HomeAssistant):
    """Set up the shopping list."""

    entry = MockConfigEntry(domain="shopping_list")
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    await sl_intent.async_setup_intents(hass)


@pytest.fixture
async def init_integration(hass: HomeAssistant):
    """Sets up the integration for testing entities"""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
