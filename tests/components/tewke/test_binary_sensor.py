"""Test Tewke binary sensor."""

from unittest.mock import AsyncMock

import pytest
from pytewke.data import ConfigData, RadarData, SensorData
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def mock_tap_with_binary_sensors(mock_tap):
    """Mock tap with binary sensor data."""
    mock_tap.get_sensors = AsyncMock(
        return_value=SensorData.model_construct(
            run_in_status=True,
            stabilisation_status=False,
        )
    )
    mock_tap.get_config = AsyncMock(
        return_value=ConfigData.model_construct(
            hardware_id="hw123",
            screen_on=True,
        )
    )
    mock_tap.get_radar = AsyncMock(
        return_value=RadarData.model_construct(
            screen_on=False,
        )
    )
    return mock_tap


async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_tap_with_binary_sensors,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation and values of the Tewke binary sensors."""
    mock_config_entry.add_to_hass(hass)

    # Enable disabled entities BEFORE setting up the entry
    entity_registry.async_get_or_create(
        "binary_sensor",
        "tewke",
        "hw123_sensor_stabilisation_status",
        suggested_object_id="living_room_tewke_switch_stabilisation_status",
        disabled_by=None,
    )
    entity_registry.async_get_or_create(
        "binary_sensor",
        "tewke",
        "hw123_sensor_run_in_status",
        suggested_object_id="living_room_tewke_switch_run_in_status",
        disabled_by=None,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    binary_sensor_entities = [ent for ent in entities if ent.domain == "binary_sensor"]

    assert len(binary_sensor_entities) == 3

    for entity_entry in binary_sensor_entities:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        state = hass.states.get(entity_entry.entity_id)
        assert state is not None
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_binary_sensor_data_becomes_none(
    hass: HomeAssistant,
    mock_tap_with_binary_sensors: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor behavior when data is missing."""
    mock_tap = mock_tap_with_binary_sensors

    mock_config_entry.add_to_hass(hass)

    # Enable disabled entities BEFORE setting up the entry
    entity_registry.async_get_or_create(
        "binary_sensor",
        "tewke",
        "hw123_sensor_stabilisation_status",
        suggested_object_id="living_room_tewke_switch_stabilisation_status",
        disabled_by=None,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Now make the endpoints return None
    mock_tap.get_sensors.return_value = None
    mock_tap.get_config.return_value = ConfigData.model_construct(
        hardware_id="hw123", screen_on=None
    )
    mock_tap.get_radar.return_value = RadarData.model_construct(screen_on=None)

    # Fast forward to trigger coordinator update
    coordinator = mock_config_entry.runtime_data.coordinator
    coordinator.async_set_updated_data(
        {
            **coordinator.data,
            "sensors": None,
            "config": ConfigData.model_construct(hardware_id="hw123", screen_on=None),
            "radar": RadarData.model_construct(screen_on=None),
        }
    )
    await hass.async_block_till_done()

    state = hass.states.get(
        "binary_sensor.living_room_tewke_switch_stabilisation_status"
    )
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("binary_sensor.living_room_tewke_switch_screen")
    assert state is not None
    assert state.state == STATE_UNKNOWN
