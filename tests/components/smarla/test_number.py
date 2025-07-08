"""Test number platform for Swing2Sleep Smarla integration."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, update_property_listeners

from tests.common import MockConfigEntry, snapshot_platform

NUMBER_ENTITIES = [
    {
        "entity_id": "number.smarla_intensity",
        "service": "babywiege",
        "property": "intensity",
    },
]


@pytest.mark.usefixtures("mock_federwiege")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Smarla entities."""
    with (
        patch("homeassistant.components.smarla.PLATFORMS", [Platform.NUMBER]),
    ):
        assert await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("service", "parameter"),
    [(SERVICE_SET_VALUE, 100)],
)
@pytest.mark.parametrize("entity_info", NUMBER_ENTITIES)
async def test_number_action(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
    entity_info: dict[str, str],
    service: str,
    parameter: int,
) -> None:
    """Test Smarla Number set behavior."""
    assert await setup_integration(hass, mock_config_entry)

    mock_number_property = mock_federwiege.get_property(
        entity_info["service"], entity_info["property"]
    )

    entity_id = entity_info["entity_id"]

    # Turn on
    await hass.services.async_call(
        NUMBER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: parameter},
        blocking=True,
    )
    mock_number_property.set.assert_called_once_with(parameter)


@pytest.mark.parametrize("entity_info", NUMBER_ENTITIES)
async def test_number_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
    entity_info: dict[str, str],
) -> None:
    """Test Smarla Number callback."""
    assert await setup_integration(hass, mock_config_entry)

    mock_number_property = mock_federwiege.get_property(
        entity_info["service"], entity_info["property"]
    )

    entity_id = entity_info["entity_id"]

    assert hass.states.get(entity_id).state == "1.0"

    mock_number_property.get.return_value = 100

    await update_property_listeners(mock_number_property)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "100.0"
