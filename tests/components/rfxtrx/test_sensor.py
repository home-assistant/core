"""The tests for the Rfxtrx sensor platform."""
from homeassistant.const import TEMP_CELSIUS, UNIT_PERCENTAGE
from homeassistant.setup import async_setup_component

from . import _signal_event


async def test_default_config(hass, rfxtrx):
    """Test with 0 sensor."""
    await async_setup_component(
        hass, "sensor", {"sensor": {"platform": "rfxtrx", "devices": {}}}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0


async def test_one_sensor(hass, rfxtrx):
    """Test with 1 sensor."""
    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "rfxtrx",
                "devices": {
                    "0a52080705020095220269": {
                        "name": "Test",
                        "data_type": "Temperature",
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_temperature")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == "Test Temperature"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS


async def test_one_sensor_no_datatype(hass, rfxtrx):
    """Test with 1 sensor."""
    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "rfxtrx",
                "devices": {"0a52080705020095220269": {"name": "Test"}},
            }
        },
    )
    await hass.async_block_till_done()

    base_id = "sensor.test"
    base_name = "Test"

    state = hass.states.get(f"{base_id}_temperature")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == f"{base_name} Temperature"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS

    state = hass.states.get(f"{base_id}_humidity")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == f"{base_name} Humidity"
    assert state.attributes.get("unit_of_measurement") == UNIT_PERCENTAGE

    state = hass.states.get(f"{base_id}_humidity_status")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == f"{base_name} Humidity status"
    assert state.attributes.get("unit_of_measurement") == ""

    state = hass.states.get(f"{base_id}_rssi_numeric")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == f"{base_name} Rssi numeric"
    assert state.attributes.get("unit_of_measurement") == "dBm"

    state = hass.states.get(f"{base_id}_battery_numeric")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == f"{base_name} Battery numeric"
    assert state.attributes.get("unit_of_measurement") == UNIT_PERCENTAGE


async def test_several_sensors(hass, rfxtrx):
    """Test with 3 sensors."""
    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "rfxtrx",
                "devices": {
                    "0a52080705020095220269": {
                        "name": "Test",
                        "data_type": "Temperature",
                    },
                    "0a520802060100ff0e0269": {
                        "name": "Bath",
                        "data_type": ["Temperature", "Humidity"],
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_temperature")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == "Test Temperature"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS

    state = hass.states.get("sensor.bath_temperature")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == "Bath Temperature"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS

    state = hass.states.get("sensor.bath_humidity")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == "Bath Humidity"
    assert state.attributes.get("unit_of_measurement") == UNIT_PERCENTAGE


async def test_discover_sensor(hass, rfxtrx):
    """Test with discovery of sensor."""
    await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "rfxtrx", "automatic_add": True, "devices": {}}},
    )
    await hass.async_block_till_done()

    # 1
    await _signal_event(hass, "0a520801070100b81b0279")
    base_id = "sensor.0a520801070100b81b0279"

    state = hass.states.get(f"{base_id}_humidity")
    assert state
    assert state.state == "27"
    assert state.attributes.get("unit_of_measurement") == UNIT_PERCENTAGE

    state = hass.states.get(f"{base_id}_humidity_status")
    assert state
    assert state.state == "normal"
    assert state.attributes.get("unit_of_measurement") == ""

    state = hass.states.get(f"{base_id}_rssi_numeric")
    assert state
    assert state.state == "-64"
    assert state.attributes.get("unit_of_measurement") == "dBm"

    state = hass.states.get(f"{base_id}_temperature")
    assert state
    assert state.state == "18.4"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS

    state = hass.states.get(f"{base_id}_battery_numeric")
    assert state
    assert state.state == "90"
    assert state.attributes.get("unit_of_measurement") == UNIT_PERCENTAGE

    # 2
    await _signal_event(hass, "0a52080405020095240279")
    base_id = "sensor.0a52080405020095240279"
    state = hass.states.get(f"{base_id}_humidity")

    assert state
    assert state.state == "36"
    assert state.attributes.get("unit_of_measurement") == UNIT_PERCENTAGE

    state = hass.states.get(f"{base_id}_humidity_status")
    assert state
    assert state.state == "normal"
    assert state.attributes.get("unit_of_measurement") == ""

    state = hass.states.get(f"{base_id}_rssi_numeric")
    assert state
    assert state.state == "-64"
    assert state.attributes.get("unit_of_measurement") == "dBm"

    state = hass.states.get(f"{base_id}_temperature")
    assert state
    assert state.state == "14.9"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS

    state = hass.states.get(f"{base_id}_battery_numeric")
    assert state
    assert state.state == "90"
    assert state.attributes.get("unit_of_measurement") == UNIT_PERCENTAGE

    # 1 Update
    await _signal_event(hass, "0a52085e070100b31b0279")
    base_id = "sensor.0a520801070100b81b0279"

    state = hass.states.get(f"{base_id}_humidity")
    assert state
    assert state.state == "27"
    assert state.attributes.get("unit_of_measurement") == UNIT_PERCENTAGE

    state = hass.states.get(f"{base_id}_humidity_status")
    assert state
    assert state.state == "normal"
    assert state.attributes.get("unit_of_measurement") == ""

    state = hass.states.get(f"{base_id}_rssi_numeric")
    assert state
    assert state.state == "-64"
    assert state.attributes.get("unit_of_measurement") == "dBm"

    state = hass.states.get(f"{base_id}_temperature")
    assert state
    assert state.state == "17.9"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS

    state = hass.states.get(f"{base_id}_battery_numeric")
    assert state
    assert state.state == "90"
    assert state.attributes.get("unit_of_measurement") == UNIT_PERCENTAGE

    assert len(hass.states.async_all()) == 10


async def test_discover_sensor_noautoadd(hass, rfxtrx):
    """Test with discover of sensor when auto add is False."""
    await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "rfxtrx", "automatic_add": False, "devices": {}}},
    )
    await hass.async_block_till_done()

    await _signal_event(hass, "0a520801070100b81b0279")
    assert len(hass.states.async_all()) == 0

    await _signal_event(hass, "0a52080405020095240279")
    assert len(hass.states.async_all()) == 0

    await _signal_event(hass, "0a52085e070100b31b0279")
    assert len(hass.states.async_all()) == 0


async def test_update_of_sensors(hass, rfxtrx):
    """Test with 3 sensors."""
    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "rfxtrx",
                "devices": {
                    "0a52080705020095220269": {
                        "name": "Test",
                        "data_type": "Temperature",
                    },
                    "0a520802060100ff0e0269": {
                        "name": "Bath",
                        "data_type": ["Temperature", "Humidity"],
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_temperature")
    assert state
    assert state.state == "unknown"

    state = hass.states.get("sensor.bath_temperature")
    assert state
    assert state.state == "unknown"

    state = hass.states.get("sensor.bath_humidity")
    assert state
    assert state.state == "unknown"

    assert len(hass.states.async_all()) == 3

    await _signal_event(hass, "0a520802060101ff0f0269")
    await _signal_event(hass, "0a52080705020085220269")

    state = hass.states.get("sensor.test_temperature")
    assert state
    assert state.state == "13.3"

    state = hass.states.get("sensor.bath_temperature")
    assert state
    assert state.state == "51.1"

    state = hass.states.get("sensor.bath_humidity")
    assert state
    assert state.state == "15"

    assert len(hass.states.async_all()) == 3
