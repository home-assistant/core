"""Test Enphase Envoy diagnostics."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.number import SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.enphase_envoy import setup_with_selected_platforms


async def test_number(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
) -> None:
    """Test enphase_envoy number entities."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.NUMBER])

    # number entities states should be created from test data
    assert len(hass.states.async_all()) == 7

    entity_registry = er.async_get(hass)
    assert entity_registry

    # compare registered entities against snapshot of prior run
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries
    assert entity_entries == snapshot

    # Test if all entities still have same state
    for entity_entry in entity_entries:
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )


@pytest.mark.parametrize(
    ("entity_id", "initial_value", "expected_value"),
    [
        ("number.enpower_654321_reserve_battery_level", "15.0", 40),
    ],
)
async def test_number_operation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    mock_set_reserve_soc: AsyncMock,
    entity_id: str,
    initial_value: str,
    expected_value: float,
) -> None:
    """Test enphase_envoy switch entities operation."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.NUMBER])

    # verify initial value
    switch_state = hass.states.get(entity_id)
    assert switch_state.state == initial_value

    await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            "value": expected_value,
        },
        blocking=True,
    )

    mock_set_reserve_soc.assert_awaited_once()
    mock_set_reserve_soc.assert_called_with(expected_value)
    mock_set_reserve_soc.reset_mock()
