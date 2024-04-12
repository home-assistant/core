"""Tests for the AirGradient sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from airgradient import AirGradientError, Measures
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.airgradient import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert entity_entries
    for entity_entry in entity_entries:
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")


async def test_create_entities(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creating entities."""
    mock_airgradient_client.get_current_measures.return_value = Measures.from_json(
        load_fixture("measures_after_boot.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)

    assert len(hass.states.async_all()) == 0
    mock_airgradient_client.get_current_measures.return_value = Measures.from_json(
        load_fixture("current_measures.json", DOMAIN)
    )
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 9


async def test_connection_error(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test connection error."""
    await setup_integration(hass, mock_config_entry)

    mock_airgradient_client.get_current_measures.side_effect = AirGradientError()
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.airgradient_humidity").state == STATE_UNAVAILABLE
