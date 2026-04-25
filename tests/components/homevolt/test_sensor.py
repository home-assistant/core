"""Tests for the Homevolt sensor platform."""

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homevolt.const import DOMAIN, SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "init_integration"
)


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "40580137858664_ems_40580137858664")}
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


async def test_sensor_exposes_values_from_coordinator(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_homevolt_client,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure sensor entities are created and expose values from the coordinator."""
    unique_id = "40580137858664_l1_voltage"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 234.0

    mock_homevolt_client.sensors["l1_voltage"].value = 240.1
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 240.1
