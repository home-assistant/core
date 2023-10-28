"""Tests for Picnic Tasks todo platform."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_cart_list_with_items(hass: HomeAssistant, init_integration) -> None:
    """Test loading of shopping cart."""
    state = hass.states.get("todo.mock_title_shopping_cart")
    assert state
    assert state.state == "10"


async def test_cart_list_empty_items(
    hass: HomeAssistant, mock_picnic_api: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading of shopping cart without items."""
    mock_picnic_api.get_cart.return_value = {"items": []}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("todo.mock_title_shopping_cart")
    assert state
    assert state.state == "0"


async def test_cart_list_unexpected_response(
    hass: HomeAssistant, mock_picnic_api: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading of shopping cart without expected response."""
    mock_picnic_api.get_cart.return_value = {}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("todo.mock_title_shopping_cart")
    assert state is None


async def test_cart_list_null_response(
    hass: HomeAssistant, mock_picnic_api: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading of shopping cart without response."""
    mock_picnic_api.get_cart.return_value = None
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("todo.mock_title_shopping_cart")
    assert state is None
