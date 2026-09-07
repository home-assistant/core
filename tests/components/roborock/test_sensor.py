"""Test Roborock Sensors."""

from typing import Any

import pytest
from roborock.data.v1 import RoborockDockTypeCode
from roborock.device_features import RoborockDockFeatures
from roborock.exceptions import RoborockException
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.roborock.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FakeDevice

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.SENSOR]


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensors and check test values are correctly set."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_entry.entry_id)


def setup_coordinator_side_effect(
    fake_devices: list[FakeDevice], side_effect: Any
) -> None:
    """Set the query/refresh side effect on all fake devices to simulate failure or delay."""
    for device in fake_devices:
        if device.v1_properties is not None:
            device.v1_properties.status.refresh.side_effect = side_effect
        if device.dyad is not None:
            device.dyad.query_values.side_effect = side_effect
        if device.zeo is not None:
            device.zeo.query_values.side_effect = side_effect
        if device.b01_q10_properties is not None:
            device.b01_q10_properties.refresh.side_effect = side_effect
        if device.b01_q7_properties is not None:
            device.b01_q7_properties.query_values.side_effect = side_effect


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (RoborockException("Simulated failure"), STATE_UNAVAILABLE),
    ],
)
async def test_sensors_coordinator_state(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_devices: list[FakeDevice],
    side_effect: Any,
    expected_state: str,
) -> None:
    """Test sensors state based on coordinator update success or delay."""
    setup_coordinator_side_effect(fake_devices, side_effect)

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    # V1 sensors
    state = hass.states.get("sensor.roborock_s7_maxv_battery")
    assert state is not None
    assert state.state == expected_state

    # A01 (Dyad/Zeo) sensors
    state = hass.states.get("sensor.dyad_pro_battery")
    assert state is not None
    assert state.state == expected_state

    state = hass.states.get("sensor.zeo_one_washing_left")
    assert state is not None
    assert state.state == expected_state

    # B01 Q7 sensors
    state = hass.states.get("sensor.roborock_q7_battery")
    assert state is not None
    assert state.state == expected_state

    # B01 Q10 sensors
    state = hass.states.get("sensor.roborock_q10_s5_battery")
    assert state is not None
    assert state.state == expected_state


async def test_dock_cleaning_brush_sensor_not_created_and_cleaned_up(
    hass: HomeAssistant,
    bypass_api_client_fixture: None,
    entity_registry: er.EntityRegistry,
    mock_roborock_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test cleaning brush sensor is not created and removed if it was in the registry."""
    fake_vacuum.v1_properties.device_features.dock_features = (
        RoborockDockFeatures.from_dock_type(RoborockDockTypeCode.pearl_dock)
    )
    entity_registry.async_get_or_create(
        domain=Platform.SENSOR,
        platform=DOMAIN,
        unique_id="cleaning_brush_time_left_abc123",
        config_entry=mock_roborock_entry,
    )
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, "cleaning_brush_time_left_abc123"
        )
        is not None
    )

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    # Cleaning brush sensor must be removed from the entity registry
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, "cleaning_brush_time_left_abc123"
        )
        is None
    )
    assert (
        hass.states.get("sensor.roborock_s7_maxv_dock_maintenance_brush_time_left")
        is None
    )
    # Washable dock strainer sensor must still exist
    assert (
        hass.states.get("sensor.roborock_s7_maxv_dock_strainer_time_left") is not None
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dock_cleaning_brush_sensor_created_when_supported(
    hass: HomeAssistant,
    bypass_api_client_fixture: None,
    mock_roborock_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test cleaning brush sensor is created on a dock that supports it."""
    fake_vacuum.v1_properties.device_features.dock_features = (
        RoborockDockFeatures.from_dock_type(RoborockDockTypeCode.o3_plus_dock)
    )
    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.roborock_s7_maxv_dock_maintenance_brush_time_left")
    assert state is not None
    assert state.state == "235"
