"""Tests for Picnic Tasks todo platform."""

from unittest.mock import MagicMock, Mock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.todo import ATTR_ITEM, DOMAIN as TODO_DOMAIN, TodoServices
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import ENTITY_ID

from tests.common import MockConfigEntry


async def test_cart_list_with_items(
    hass: HomeAssistant,
    init_integration,
    get_items,
    snapshot: SnapshotAssertion,
) -> None:
    """Test loading of shopping cart."""
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == "10"

    assert snapshot == await get_items()


async def test_cart_list_empty_items(
    hass: HomeAssistant, mock_picnic_api: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading of shopping cart without items."""
    mock_picnic_api.get_cart.return_value = {"items": []}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
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

    state = hass.states.get(ENTITY_ID)
    assert state is None


async def test_cart_list_null_response(
    hass: HomeAssistant, mock_picnic_api: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading of shopping cart without response."""
    mock_picnic_api.get_cart.return_value = None
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is None


async def test_create_todo_list_item(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_picnic_api: MagicMock
) -> None:
    """Test for creating a picnic cart item."""
    assert len(mock_picnic_api.get_cart.mock_calls) == 1

    mock_picnic_api.search = Mock()
    mock_picnic_api.search.return_value = [
        {
            "items": [
                {
                    "id": 321,
                    "name": "Picnic Melk",
                    "unit_quantity": "2 liter",
                }
            ]
        }
    ]

    mock_picnic_api.add_product = Mock()

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ITEM: "Melk"},
        target={ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    args = mock_picnic_api.search.call_args
    assert args
    assert args[0][0] == "Melk"

    args = mock_picnic_api.add_product.call_args
    assert args
    assert args[0][0] == "321"
    assert args[0][1] == 1

    assert len(mock_picnic_api.get_cart.mock_calls) == 2


async def test_create_todo_list_item_not_found(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_picnic_api: MagicMock
) -> None:
    """Test for creating a picnic cart item when ID is not found."""
    mock_picnic_api.search = Mock()
    mock_picnic_api.search.return_value = [{"items": []}]

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.ADD_ITEM,
            {ATTR_ITEM: "Melk"},
            target={ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
