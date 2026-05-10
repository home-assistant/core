"""Tests for the Fumis sensor entities."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import UNIQUE_ID

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
    "unique_id",
    [
        f"{UNIQUE_ID}_fan_1_speed",
        f"{UNIQUE_ID}_fan_2_speed",
        f"{UNIQUE_ID}_module_temperature",
        f"{UNIQUE_ID}_pressure",
        f"{UNIQUE_ID}_wifi_rssi",
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_sensors_disabled_by_default(
    entity_registry: er.EntityRegistry,
    unique_id: str,
) -> None:
    """Test sensors that are disabled by default."""
    entry = entity_registry.async_get_entity_id("sensor", "fumis", unique_id)
    assert entry is not None, f"Entity with unique_id {unique_id} not found"
    assert (entity_entry := entity_registry.async_get(entry))
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("device_fixture", ["info_minimal"])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors_unknown_status(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor returns unknown when stove status is unmapped."""
    for key in ("stove_status", "detailed_stove_status"):
        entry = entity_registry.async_get_entity_id(
            "sensor", "fumis", f"{UNIQUE_ID}_{key}"
        )
        assert entry is not None
        assert (state := hass.states.get(entry))
        assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("device_fixture", ["info_error_alert"])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors_active_error_and_alert(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test error and alert sensors with active codes."""
    error_entity_id = entity_registry.async_get_entity_id(
        "sensor", "fumis", f"{UNIQUE_ID}_error"
    )
    assert error_entity_id is not None
    assert (state := hass.states.get(error_entity_id))
    assert state == snapshot
    assert state.state == "ignition_failed"
    assert state.attributes["code"] == "E101"

    alert_entity_id = entity_registry.async_get_entity_id(
        "sensor", "fumis", f"{UNIQUE_ID}_alert"
    )
    assert alert_entity_id is not None
    assert (state := hass.states.get(alert_entity_id))
    assert state == snapshot
    assert state.state == "low_fuel"
    assert state.attributes["code"] == "A001"


@pytest.mark.parametrize("device_fixture", ["info_minimal"])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors_conditional_creation(
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors with has_fn are not created when data is missing."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    unique_ids = {entry.unique_id for entry in entity_entries}

    # These should NOT exist with the minimal fixture
    for key in (
        "combustion_chamber_temperature",
        "fan_1_speed",
        "fan_2_speed",
        "fuel_quantity",
        "module_temperature",
        "pressure",
        "temperature",
        "time_to_service",
    ):
        assert f"{UNIQUE_ID}_{key}" not in unique_ids, key

    # These should still exist
    for key in (
        "alert",
        "detailed_stove_status",
        "error",
        "power_output",
        "stove_status",
        "wifi_rssi",
        "wifi_signal_strength",
    ):
        assert f"{UNIQUE_ID}_{key}" in unique_ids, key
