from unittest.mock import AsyncMock

import pytest
from pytewke.data import ConfigData, EnergyData, RadarData, SensorData
from pytewke.data.radar import RadarProximity, RadarThreshold, RadarThresholds
from pytewke.data.sensors import AmbientLight
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

from homeassistant.components.tewke.sensor import (
    ENERGY_SENSOR_DESCRIPTIONS,
    RADAR_SENSOR_DESCRIPTIONS,
    SENSOR_DESCRIPTIONS,
)

@pytest.fixture
def mock_tap_with_sensors(mock_tap):
    """Mock tap with sensor data."""
    mock_tap.get_sensors = AsyncMock(
        return_value=SensorData(
            iaq=50,
            rawGas=1000.0,
            staticIaq=40,
            iaqAccuracy=3,
            rawHumidity=50.0,
            rawPressure=1000.0,
            runInStatus=True,
            co2Equivalent=400,
            gasPercentage=20,
            rawTemperature=22.0,
            breathVocEquivalent=0.5,
            compensatedHumidity=45.0,
            stabilisationStatus=True,
            compensatedTemperature=21.0,
            ambientLight=AmbientLight(lux=300.0),
        )
    )
    mock_tap.get_radar = AsyncMock(
        return_value=RadarData(
            proximity="near",
            screenOn=True,
            thresholds=None,
        )
    )
    mock_tap.get_energy = AsyncMock(
        return_value=EnergyData(
            power=100.0,
            actualPower=95.0,
            override=None,
            hasOverride=False,
        )
    )
    mock_tap.tewke_os_version = "1.0.0"
    mock_tap.get_config = AsyncMock(
        return_value=ConfigData(
            roomId="room1",
            roomName="Living Room",
            deviceName="My Tap",
            hardwareId="hw123",
            tewkeOsVersion="1.0.0",
        )
    )
    return mock_tap


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_tap_with_sensors,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation and values of the Tewke sensors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get all entities for the config entry
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    # Filter to only sensor domain
    sensor_entities = [ent for ent in entities if ent.domain == "sensor"]

    assert len(sensor_entities) > 0

    # Enable all disabled entities
    for entity_entry in sensor_entities:
        if entity_entry.disabled_by:
            entity_registry.async_update_entity(
                entity_entry.entity_id, disabled_by=None
            )

    # Reload the config entry to create the newly enabled entities
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for entity_entry in sensor_entities:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        state = hass.states.get(entity_entry.entity_id)
        assert state is not None
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_sensor_data_becomes_none(
    hass: HomeAssistant,
    mock_tap: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor behavior when data becomes None after initialization."""
    # First initialize with valid data
    sensors = SensorData.model_construct(
        iaq=100.0,
        staticIaq=100.0,
        compensatedTemperature=20.0,
        compensatedHumidity=50.0,
        co2Equivalent=400.0,
        rawPressure=101325.0,
        gasPercentage=50.0,
        ambientLight=AmbientLight.model_construct(lux=100.0),
        iaqAccuracy=3,
        breathVocEquivalent=0.5,
        rawTemperature=20.0,
        rawHumidity=50.0,
        rawGas=50000.0,
    )
    radar = RadarData.model_construct(
        proximity=RadarProximity.NEAR,
        thresholds=RadarThresholds.model_construct(
            near=RadarThreshold.model_construct(value=100, hysteresis=10),
            far=RadarThreshold.model_construct(value=200, hysteresis=20),
        ),
    )
    energy = EnergyData.model_construct(
        power=10.0,
        actualPower=10.0,
    )
    mock_tap.get_sensors.return_value = sensors
    mock_tap.get_radar.return_value = radar
    mock_tap.get_energy.return_value = energy

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Now make the endpoints return None
    mock_tap.get_sensors.return_value = None
    mock_tap.get_radar.return_value = None
    mock_tap.get_energy.return_value = None

    # Fast forward to trigger coordinator update
    coordinator = mock_config_entry.runtime_data.coordinator
    coordinator.async_set_updated_data(
        {
            **coordinator.data,
            "sensors": None,
            "radar": None,
            "energy": None,
        }
    )
    await hass.async_block_till_done()

    # Entities should now report 'unavailable' state because native_value returns None
    state = hass.states.get("sensor.living_room_tewke_switch_air_quality")
    print("STATE:", state)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.living_room_tewke_switch_radar_proximity")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.living_room_tewke_switch_power")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_missing_optional_data(
    hass: HomeAssistant,
    mock_tap_with_sensors: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensors when optional data is missing."""
    mock_tap = mock_tap_with_sensors
    # Keep the root objects but set optional fields to None
    mock_tap.get_sensors.return_value = SensorData(
        iaq=50,
        rawGas=1000.0,
        staticIaq=40,
        iaqAccuracy=3,
        rawHumidity=50.0,
        rawPressure=1000.0,
        runInStatus=True,
        co2Equivalent=400,
        gasPercentage=20,
        rawTemperature=22.0,
        breathVocEquivalent=0.5,
        compensatedHumidity=45.0,
        stabilisationStatus=True,
        compensatedTemperature=21.0,
        ambientLight=None,  # Missing optional field
    )
    mock_tap.get_radar.return_value = RadarData(
        proximity="near",
        screenOn=True,
        thresholds=None,  # Missing optional field
    )
    mock_tap.get_energy.return_value = EnergyData(
        power=100.0,
        actualPower=95.0,
        override=None,
        hasOverride=False,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    sensor_entities = [
        ent
        for ent in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if ent.domain == "sensor"
    ]

    assert len(sensor_entities) > 0

    # Enable all disabled entities
    for entity_entry in sensor_entities:
        if entity_entry.disabled_by:
            entity_registry.async_update_entity(
                entity_entry.entity_id, disabled_by=None
            )

    # Reload the config entry to create the newly enabled entities
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The entities should be created, and some states will be unknown due to missing optional fields
    for entity_entry in sensor_entities:
        state = hass.states.get(entity_entry.entity_id)
        assert state is not None
        # We don't necessarily assert state is unknown for ALL of them, just that they load without error
        # The specific ones with missing data (like ambient_light) will be unknown


async def test_native_value_when_none(
    hass: HomeAssistant,
    mock_tap_with_sensors,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that native_value returns None when data is missing."""
    mock_tap = mock_tap_with_sensors
    mock_tap.get_sensors.return_value = None
    mock_tap.get_radar.return_value = None
    mock_tap.get_energy.return_value = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The entities will still be registered but unavailable
    # Let's get the objects and call native_value directly
    from homeassistant.components.tewke.sensor import (
        TewkeEnergySensor,
        TewkeRadarSensor,
        TewkeSensor,
    )

    coordinator = mock_config_entry.runtime_data.coordinator

    # Just need to fetch the entity objects. Wait, HA doesn't expose the entity objects easily.
    # We can just instantiate them directly for the test.
    # 1. Sensor
    sensor = TewkeSensor(coordinator, SENSOR_DESCRIPTIONS[0])
    assert sensor.native_value is None

    # 2. Radar
    radar = TewkeRadarSensor(coordinator, RADAR_SENSOR_DESCRIPTIONS[0])
    assert radar.native_value is None

    # 3. Energy
    energy = TewkeEnergySensor(coordinator, ENERGY_SENSOR_DESCRIPTIONS[0])
    assert energy.native_value is None
