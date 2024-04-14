"""Common fixtures for the OurGroceries tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.ourgroceries import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import items_to_shopping_list

from tests.common import MockConfigEntry

USERNAME = "test-username"
PASSWORD = "test-password"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ourgroceries.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="ourgroceries_config_entry")
def mock_ourgroceries_config_entry() -> MockConfigEntry:
    """Mock ourgroceries configuration."""
    return MockConfigEntry(
        domain=DOMAIN, data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )


@pytest.fixture(name="items")
def mock_items() -> dict:
    """Mock a collection of shopping list items."""
    return []


@pytest.fixture(name="ourgroceries")
def mock_ourgroceries(items: list[dict]) -> AsyncMock:
    """Mock the OurGroceries api."""
    og = AsyncMock()
    og.login.return_value = True
    og.get_my_lists.return_value = {
        "shoppingLists": [{"id": "test_list", "name": "Test List", "versionId": "1"}]
    }
    og.get_list_items.return_value = items_to_shopping_list(items)
    return og


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    ourgroceries: AsyncMock,
    ourgroceries_config_entry: MockConfigEntry,
) -> None:
    """Mock setup of the ourgroceries integration."""
    ourgroceries_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.ourgroceries.OurGroceries", return_value=ourgroceries
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield
