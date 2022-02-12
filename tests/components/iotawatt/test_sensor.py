"""Test setting up sensors."""
from datetime import timedelta

from homeassistant.components.iotawatt.const import ATTR_LAST_UPDATE
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    ENERGY_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.core import State
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import (
    INPUT_ACCUMULATED_SENSOR,
    INPUT_SENSOR,
    OUTPUT_ACCUMULATED_SENSOR,
    OUTPUT_SENSOR,
)

from tests.common import async_fire_time_changed, mock_restore_cache


async def test_sensor_type_input(hass, mock_iotawatt):
    """Test input sensors work."""
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 0

    # Discover this sensor during a regular update.
    mock_iotawatt.getSensors.return_value["sensors"]["my_sensor_key"] = INPUT_SENSOR
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1

    state = hass.states.get("sensor.my_sensor")
    assert state is not None
    assert state.state == "23"
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.MEASUREMENT
    assert state.attributes[ATTR_FRIENDLY_NAME] == "My Sensor"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == POWER_WATT
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.POWER
    assert state.attributes["channel"] == "1"
    assert state.attributes["type"] == "Input"

    mock_iotawatt.getSensors.return_value["sensors"].pop("my_sensor_key")
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    assert hass.states.get("sensor.my_sensor") is None


async def test_sensor_type_output(hass, mock_iotawatt):
    """Tests the sensor type of Output."""
    mock_iotawatt.getSensors.return_value["sensors"][
        "my_watthour_sensor_key"
    ] = OUTPUT_SENSOR
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1

    state = hass.states.get("sensor.my_watthour_sensor")
    assert state is not None
    assert state.state == "243"
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.TOTAL
    assert state.attributes[ATTR_FRIENDLY_NAME] == "My WattHour Sensor"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == ENERGY_WATT_HOUR
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENERGY
    assert state.attributes["type"] == "Output"

    mock_iotawatt.getSensors.return_value["sensors"].pop("my_watthour_sensor_key")
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    assert hass.states.get("sensor.my_watthour_sensor") is None


async def test_sensor_type_accumulated_output(hass, mock_iotawatt):
    """Tests the sensor type of Accumulated Output and that it's properly restored from saved state."""
    mock_iotawatt.getSensors.return_value["sensors"][
        "my_watthour_accumulated_output_sensor_key"
    ] = OUTPUT_ACCUMULATED_SENSOR

    DUMMY_DATE = "2021-09-01T14:00:00+10:00"

    mock_restore_cache(
        hass,
        (
            State(
                "sensor.my_watthour_accumulated_output_sensor_wh_accumulated",
                "100.0",
                {
                    "device_class": SensorDeviceClass.ENERGY,
                    "unit_of_measurement": ENERGY_WATT_HOUR,
                    "last_update": DUMMY_DATE,
                },
            ),
        ),
    )

    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1

    state = hass.states.get(
        "sensor.my_watthour_accumulated_output_sensor_wh_accumulated"
    )
    assert state is not None

    assert state.state == "300.0"  # 100 + 200
    assert (
        state.attributes[ATTR_FRIENDLY_NAME]
        == "My WattHour Accumulated Output Sensor.wh Accumulated"
    )
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.TOTAL
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == ENERGY_WATT_HOUR
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENERGY
    assert state.attributes["type"] == "Output"
    assert state.attributes[ATTR_LAST_UPDATE] is not None
    assert state.attributes[ATTR_LAST_UPDATE] != DUMMY_DATE


async def test_sensor_type_accumulated_output_error_restore(hass, mock_iotawatt):
    """Tests the sensor type of Accumulated Output and that it's properly restored from saved state."""
    mock_iotawatt.getSensors.return_value["sensors"][
        "my_watthour_accumulated_output_sensor_key"
    ] = OUTPUT_ACCUMULATED_SENSOR

    DUMMY_DATE = "2021-09-01T14:00:00+10:00"

    mock_restore_cache(
        hass,
        (
            State(
                "sensor.my_watthour_accumulated_output_sensor_wh_accumulated",
                "unknown",
            ),
        ),
    )

    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1

    state = hass.states.get(
        "sensor.my_watthour_accumulated_output_sensor_wh_accumulated"
    )
    assert state is not None

    assert state.state == "200.0"  # Returns the new read as restore failed.
    assert (
        state.attributes[ATTR_FRIENDLY_NAME]
        == "My WattHour Accumulated Output Sensor.wh Accumulated"
    )
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.TOTAL
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == ENERGY_WATT_HOUR
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENERGY
    assert state.attributes["type"] == "Output"
    assert state.attributes[ATTR_LAST_UPDATE] is not None
    assert state.attributes[ATTR_LAST_UPDATE] != DUMMY_DATE


async def test_sensor_type_multiple_accumulated_output(hass, mock_iotawatt):
    """Tests the sensor type of Accumulated Output and that it's properly restored from saved state."""
    mock_iotawatt.getSensors.return_value["sensors"][
        "my_watthour_accumulated_output_sensor_key"
    ] = OUTPUT_ACCUMULATED_SENSOR
    mock_iotawatt.getSensors.return_value["sensors"][
        "my_watthour_accumulated_input_sensor_key"
    ] = INPUT_ACCUMULATED_SENSOR

    DUMMY_DATE = "2021-09-01T14:00:00+10:00"

    mock_restore_cache(
        hass,
        (
            State(
                "sensor.my_watthour_accumulated_output_sensor_wh_accumulated",
                "100.0",
                {
                    "device_class": SensorDeviceClass.ENERGY,
                    "unit_of_measurement": ENERGY_WATT_HOUR,
                    "last_update": DUMMY_DATE,
                },
            ),
            State(
                "sensor.my_watthour_accumulated_input_sensor_wh_accumulated",
                "50.0",
                {
                    "device_class": SensorDeviceClass.ENERGY,
                    "unit_of_measurement": ENERGY_WATT_HOUR,
                    "last_update": DUMMY_DATE,
                },
            ),
        ),
    )

    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 2

    state = hass.states.get(
        "sensor.my_watthour_accumulated_output_sensor_wh_accumulated"
    )
    assert state is not None

    assert state.state == "300.0"  # 100 + 200
    assert (
        state.attributes[ATTR_FRIENDLY_NAME]
        == "My WattHour Accumulated Output Sensor.wh Accumulated"
    )
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.TOTAL
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == ENERGY_WATT_HOUR
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENERGY
    assert state.attributes["type"] == "Output"
    assert state.attributes[ATTR_LAST_UPDATE] is not None
    assert state.attributes[ATTR_LAST_UPDATE] != DUMMY_DATE

    state = hass.states.get(
        "sensor.my_watthour_accumulated_input_sensor_wh_accumulated"
    )
    assert state is not None

    assert state.state == "550.0"  # 50 + 500
    assert (
        state.attributes[ATTR_FRIENDLY_NAME]
        == "My WattHour Accumulated Input Sensor.wh Accumulated"
    )
    assert state.attributes[ATTR_LAST_UPDATE] is not None
    assert state.attributes[ATTR_LAST_UPDATE] != DUMMY_DATE
