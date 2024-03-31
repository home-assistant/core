"""Test Enphase Envoy binary sensors."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.enphase_envoy import setup_with_selected_platforms


@pytest.mark.parametrize(
    ("mock_envoy", "entity_count"),
    [
        pytest.param("envoy_metered_batt_relay", 4, id="envoy_metered_batt_relay"),
    ],
    indirect=["mock_envoy"],
)
async def test_binary_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    entity_registry: AsyncMock,
    entity_count: int,
) -> None:
    """Test enphase_envoy binary_sensor entities."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.BINARY_SENSOR])

    # number entities states should be created from test data
    assert len(hass.states.async_all()) == entity_count
    assert entity_registry

    # compare registered entities against snapshot of prior run
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )


@pytest.mark.parametrize(
    ("mock_envoy", "entity_count"),
    [
        pytest.param("envoy", 0, id="envoy"),
    ],
    indirect=["mock_envoy"],
)
async def test_no_binary_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    entity_registry: AsyncMock,
    entity_count: int,
) -> None:
    """Test enphase_envoy switch entities."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.BINARY_SENSOR])

    # these entities states should be created enabled from test data
    assert len(hass.states.async_all()) == entity_count
