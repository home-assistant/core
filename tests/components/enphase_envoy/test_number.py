"""Test Enphase Envoy diagnostics."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.number import SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import ConfigType, MockConfigEntry


@pytest.fixture(name="setup_enphase_envoy_number")
async def setup_enphase_envoy_number_fixture(
    hass: HomeAssistant, config: ConfigType, mock_envoy: AsyncMock
):
    """Define a fixture to set up Enphase Envoy with number platform only."""
    with (
        patch(
            "homeassistant.components.enphase_envoy.Envoy",
            return_value=mock_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.PLATFORMS",
            [Platform.NUMBER],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


async def test_number(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    setup_enphase_envoy_number,
) -> None:
    """Test enphase_envoy number entities."""

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
    snapshot: SnapshotAssertion,
    setup_enphase_envoy_number: AsyncMock,
    mock_envoy: AsyncMock,
    mock_set_reserve_soc: AsyncMock,
    entity_id: str,
    initial_value: str,
    expected_value: float,
) -> None:
    """Test enphase_envoy switch entities operation."""

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
