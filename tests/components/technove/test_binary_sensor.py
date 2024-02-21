"""Tests for the TechnoVE binary sensor platform."""
from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion
from technove import TechnoVEError

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_technove")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the creation and values of the TechnoVE binary sensors."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.BINARY_SENSOR]
    )

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )


@pytest.mark.parametrize(
    "entity_id",
    ("binary_sensor.technove_station_static_ip",),
)
@pytest.mark.usefixtures("init_integration")
async def test_disabled_by_default_binary_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test the disabled by default TechnoVE binary sensors."""
    assert hass.states.get(entity_id) is None

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("init_integration")
async def test_binary_sensor_update_failure(
    hass: HomeAssistant,
    mock_technove: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator update failure."""
    entity_id = "binary_sensor.technove_station_charging"

    assert hass.states.get(entity_id).state == STATE_ON

    mock_technove.update.side_effect = TechnoVEError("Test error")
    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
