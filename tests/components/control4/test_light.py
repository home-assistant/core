"""Test Control4 Light."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.control4.const import DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

LIGHT_ITEMS = [
    {
        "id": 345,
        "name": "Kitchen Light",
        "type": 7,
        "parentId": 678,
        "categories": ["lights"],
    },
    {
        "id": 678,
        "name": "Kitchen Light",
        "type": 6,
        "manufacturer": "Control4",
        "model": "C4-SW120277",
        "categories": ["lights"],
    },
]


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms which should be loaded during the test."""
    return [Platform.LIGHT]


@pytest.fixture
def mock_light_items(mock_c4_director: MagicMock) -> None:
    """Add a light to the items reported by the director."""
    mock_c4_director.get_all_item_info.return_value = [
        *mock_c4_director.get_all_item_info.return_value,
        *LIGHT_ITEMS,
    ]


@pytest.fixture
def mock_light_variables(
    mock_c4_director: MagicMock, light_variables: list[dict[str, Any]]
) -> None:
    """Mock a director where only some light variables exist."""
    reported_names = {variable["varName"] for variable in light_variables}

    def get_all_item_variable_value(variable_names: set[str]) -> list[dict[str, Any]]:
        if not variable_names & reported_names:
            # pyControl4 raises ValueError when no item has any of the variables.
            raise ValueError("Empty response received from Director!")
        return light_variables

    mock_c4_director.get_all_item_variable_value.side_effect = (
        get_all_item_variable_value
    )


@pytest.mark.usefixtures("mock_c4_account", "mock_light_items", "mock_light_variables")
@pytest.mark.parametrize(
    "light_variables",
    [
        pytest.param(
            [{"id": 345, "varName": "LIGHT_STATE", "value": 1}],
            id="no_dimmers",
        ),
        pytest.param(
            [{"id": 345, "varName": "LIGHT_LEVEL", "value": 100}],
            id="only_dimmers",
        ),
    ],
)
async def test_light_created_when_other_light_type_missing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lights are created when the system has only one type of light."""
    await setup_integration(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(LIGHT_DOMAIN, DOMAIN, "345")
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_ON
