"""Test Enphase Envoy binary sensors."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import ConfigType, MockConfigEntry


@pytest.fixture(name="setup_enphase_envoy_binary_sensor")
async def setup_enphase_envoy_binary_sensor_fixture(
    hass: HomeAssistant, config: ConfigType, mock_envoy: AsyncMock
):
    """Define a fixture to set up Enphase Envoy with binary sensor platform only."""
    with (
        patch(
            "homeassistant.components.enphase_envoy.Envoy",
            return_value=mock_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.PLATFORMS",
            [Platform.BINARY_SENSOR],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


async def test_binary_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    setup_enphase_envoy_binary_sensor,
) -> None:
    """Test enphase_envoy binary_sensor entities."""

    # number entities states should be created from test data
    assert len(hass.states.async_all()) == 4

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
