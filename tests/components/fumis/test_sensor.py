"""Tests for the Fumis sensor entities."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.parametrize(
    "init_integration", [Platform.SENSOR], indirect=True
)


@pytest.mark.freeze_time("2026-04-20 12:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Fumis sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.clou_duo_combustion_chamber_pressure",
        "sensor.clou_duo_fan_1_speed",
        "sensor.clou_duo_fan_2_speed",
        "sensor.clou_duo_wircu_module",
        "sensor.clou_duo_wi_fi_rssi",
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_sensors_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_id: str,
) -> None:
    """Test sensors that are disabled by default."""
    assert (entry := entity_registry.async_get(entity_id))
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None


@pytest.mark.parametrize("device_fixture", ["info_minimal"])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors_unknown_status(
    hass: HomeAssistant,
) -> None:
    """Test sensor returns unknown when stove status is unmapped."""
    assert (state := hass.states.get("sensor.pellet_stove_stove_status"))
    assert state.state == STATE_UNKNOWN

    assert (state := hass.states.get("sensor.pellet_stove_detailed_stove_status"))
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("device_fixture", ["info_minimal"])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors_conditional_creation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors with has_fn are not created when data is missing."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    entity_ids = {entry.entity_id for entry in entity_entries}

    # These should NOT exist with the minimal fixture
    assert "sensor.pellet_stove_combustion_chamber_pressure" not in entity_ids
    assert "sensor.pellet_stove_combustion_chamber_temperature" not in entity_ids
    assert "sensor.pellet_stove_fan_1_speed" not in entity_ids
    assert "sensor.pellet_stove_fan_2_speed" not in entity_ids
    assert "sensor.pellet_stove_fuel_quantity" not in entity_ids
    assert "sensor.pellet_stove_module_temperature" not in entity_ids
    assert "sensor.pellet_stove_temperature" not in entity_ids
    assert "sensor.pellet_stove_time_to_service" not in entity_ids

    # These should still exist
    assert "sensor.pellet_stove_detailed_stove_status" in entity_ids
    assert "sensor.pellet_stove_power_output" in entity_ids
    assert "sensor.pellet_stove_stove_status" in entity_ids
    assert "sensor.pellet_stove_wi_fi_rssi" in entity_ids
    assert "sensor.pellet_stove_wi_fi_signal_strength" in entity_ids
