"""Tests for the PiKVM sensor platform."""

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test the PiKVM sensors."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    ("device_info", "entity_id"),
    [
        pytest.param("fan", "sensor.pikvm_fan_speed", id="no_fan"),
        pytest.param("msd", "sensor.pikvm_mass_storage_usage", id="no_mass_storage"),
    ],
    indirect=["device_info"],
)
@pytest.mark.usefixtures("init_integration")
async def test_optional_hardware_sensors_skipped(
    entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test sensors are not created for hardware the PiKVM does not have."""
    assert entity_registry.async_get(entity_id) is None
    assert entity_registry.async_get("sensor.pikvm_cpu_temperature")


@pytest.mark.parametrize("device_info", ["health"], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_core_health_sensors_created_when_unavailable(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test core health sensors are created even when initial readings are None."""
    for entity_id in (
        "sensor.pikvm_cpu_temperature",
        "sensor.pikvm_cpu_utilization",
        "sensor.pikvm_memory_utilization",
    ):
        assert entity_registry.async_get(entity_id) is not None
        assert (state := hass.states.get(entity_id)) is not None
        assert state.state == STATE_UNKNOWN
