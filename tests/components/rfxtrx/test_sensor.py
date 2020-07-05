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

    state = hass.states.get("sensor.test_temperature")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == "Test Temperature"
    assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS


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

    await _signal_event(hass, "0a520801070100b81b0279")
    state = hass.states.get("sensor.0a520801070100b81b0279_temperature")
    assert state
    assert state.state == "18.4"
    assert (
        state.attributes.items()
        >= {
            "friendly_name": "0a520801070100b81b0279 Temperature",
            "unit_of_measurement": TEMP_CELSIUS,
            "Humidity status": "normal",
            "Temperature": 18.4,
            "Rssi numeric": 7,
            "Humidity": 27,
            "Battery numeric": 9,
            "Humidity status numeric": 2,
        }.items()
    )

    await _signal_event(hass, "0a52080405020095240279")
    state = hass.states.get("sensor.0a52080405020095240279_temperature")
    assert state
    assert state.state == "14.9"
    assert (
        state.attributes.items()
        >= {
            "friendly_name": "0a52080405020095240279 Temperature",
            "unit_of_measurement": TEMP_CELSIUS,
            "Humidity status": "normal",
            "Temperature": 14.9,
            "Rssi numeric": 7,
            "Humidity": 36,
            "Battery numeric": 9,
            "Humidity status numeric": 2,
        }.items()
    )

    await _signal_event(hass, "0a52085e070100b31b0279")
    state = hass.states.get("sensor.0a520801070100b81b0279_temperature")
    assert state
    assert state.state == "17.9"
    assert (
        state.attributes.items()
        >= {
            "friendly_name": "0a520801070100b81b0279 Temperature",
            "unit_of_measurement": TEMP_CELSIUS,
            "Humidity status": "normal",
            "Temperature": 17.9,
            "Rssi numeric": 7,
            "Humidity": 27,
            "Battery numeric": 9,
            "Humidity status numeric": 2,
        }.items()
    )

    assert len(hass.states.async_all()) == 2


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
    assert (
        state.attributes.items()
        >= {
            "friendly_name": "Test Temperature",
            "unit_of_measurement": TEMP_CELSIUS,
        }.items()
    )

    state = hass.states.get("sensor.bath_temperature")
    assert state
    assert state.state == "unknown"
    assert (
        state.attributes.items()
        >= {
            "friendly_name": "Bath Temperature",
            "unit_of_measurement": TEMP_CELSIUS,
        }.items()
    )

    state = hass.states.get("sensor.bath_humidity")
    assert state
    assert state.state == "unknown"
    assert (
        state.attributes.items()
        >= {
            "friendly_name": "Bath Humidity",
            "unit_of_measurement": UNIT_PERCENTAGE,
        }.items()
    )

    assert len(hass.states.async_all()) == 3

    await _signal_event(hass, "0a520802060101ff0f0269")
    await _signal_event(hass, "0a52080705020085220269")

    state = hass.states.get("sensor.test_temperature")
    assert state
    assert state.state == "13.3"
    assert (
        state.attributes.items()
        >= {
            "friendly_name": "Test Temperature",
            "unit_of_measurement": TEMP_CELSIUS,
            "Battery numeric": 9,
            "Temperature": 13.3,
            "Humidity": 34,
            "Humidity status": "normal",
            "Humidity status numeric": 2,
            "Rssi numeric": 6,
        }.items()
    )

    state = hass.states.get("sensor.bath_temperature")
    assert state
    assert state.state == "51.1"
    assert (
        state.attributes.items()
        >= {
            "friendly_name": "Bath Temperature",
            "unit_of_measurement": TEMP_CELSIUS,
            "Battery numeric": 9,
            "Temperature": 51.1,
            "Humidity": 15,
            "Humidity status": "normal",
            "Humidity status numeric": 2,
            "Rssi numeric": 6,
        }.items()
    )

    state = hass.states.get("sensor.bath_humidity")
    assert state
    assert state.state == "15"
    assert (
        state.attributes.items()
        >= {
            "friendly_name": "Bath Humidity",
            "unit_of_measurement": UNIT_PERCENTAGE,
            "Battery numeric": 9,
            "Temperature": 51.1,
            "Humidity": 15,
            "Humidity status": "normal",
            "Humidity status numeric": 2,
            "Rssi numeric": 6,
        }.items()
    )

    assert len(hass.states.async_all()) == 3
