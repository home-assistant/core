"""The tests for the Rfxtrx sensor platform."""
from homeassistant.components import rfxtrx as rfxtrx_core
from homeassistant.const import TEMP_CELSIUS, UNIT_PERCENTAGE
from homeassistant.setup import async_setup_component

from . import _signal_event


async def test_default_config(hass, rfxtrx):
    """Test with 0 sensor."""
    await async_setup_component(
        hass, "sensor", {"sensor": {"platform": "rfxtrx", "devices": {}}}
    )
    await hass.async_block_till_done()

    assert 0 == len(rfxtrx_core.RFX_DEVICES)


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

    assert 1 == len(rfxtrx_core.RFX_DEVICES)
    entity = rfxtrx_core.RFX_DEVICES["sensor_05_02"]["Temperature"]
    assert "Test Temperature" == entity.name
    assert TEMP_CELSIUS == entity.unit_of_measurement
    assert entity.state is None


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

    assert 1 == len(rfxtrx_core.RFX_DEVICES)
    entity = rfxtrx_core.RFX_DEVICES["sensor_05_02"]["Temperature"]
    assert "Test Temperature" == entity.name
    assert TEMP_CELSIUS == entity.unit_of_measurement
    assert entity.state is None


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

    assert 2 == len(rfxtrx_core.RFX_DEVICES)
    device_num = 0
    for id in rfxtrx_core.RFX_DEVICES:
        if id == "sensor_06_01":
            device_num = device_num + 1
            assert len(rfxtrx_core.RFX_DEVICES[id]) == 2
            _entity_temp = rfxtrx_core.RFX_DEVICES[id]["Temperature"]
            _entity_hum = rfxtrx_core.RFX_DEVICES[id]["Humidity"]
            assert UNIT_PERCENTAGE == _entity_hum.unit_of_measurement
            assert "Bath" == _entity_hum.__str__()
            assert _entity_hum.state is None
            assert TEMP_CELSIUS == _entity_temp.unit_of_measurement
            assert "Bath" == _entity_temp.__str__()
        elif id == "sensor_05_02":
            device_num = device_num + 1
            entity = rfxtrx_core.RFX_DEVICES[id]["Temperature"]
            assert entity.state is None
            assert TEMP_CELSIUS == entity.unit_of_measurement
            assert "Test" == entity.__str__()

    assert 2 == device_num


async def test_discover_sensor(hass, rfxtrx):
    """Test with discovery of sensor."""
    await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "rfxtrx", "automatic_add": True, "devices": {}}},
    )
    await hass.async_block_till_done()

    event = rfxtrx_core.get_rfx_object("0a520801070100b81b0279")
    event.data = bytearray(b"\nR\x08\x01\x07\x01\x00\xb8\x1b\x02y")
    await _signal_event(hass, event)

    entity = rfxtrx_core.RFX_DEVICES["sensor_07_01"]["Temperature"]
    assert 1 == len(rfxtrx_core.RFX_DEVICES)
    assert {
        "Humidity status": "normal",
        "Temperature": 18.4,
        "Rssi numeric": 7,
        "Humidity": 27,
        "Battery numeric": 9,
        "Humidity status numeric": 2,
    } == entity.device_state_attributes
    assert "0a520801070100b81b0279" == entity.__str__()

    await _signal_event(hass, event)
    assert 1 == len(rfxtrx_core.RFX_DEVICES)

    event = rfxtrx_core.get_rfx_object("0a52080405020095240279")
    event.data = bytearray(b"\nR\x08\x04\x05\x02\x00\x95$\x02y")
    await _signal_event(hass, event)
    entity = rfxtrx_core.RFX_DEVICES["sensor_05_02"]["Temperature"]
    assert 2 == len(rfxtrx_core.RFX_DEVICES)
    assert {
        "Humidity status": "normal",
        "Temperature": 14.9,
        "Rssi numeric": 7,
        "Humidity": 36,
        "Battery numeric": 9,
        "Humidity status numeric": 2,
    } == entity.device_state_attributes
    assert "0a52080405020095240279" == entity.__str__()

    event = rfxtrx_core.get_rfx_object("0a52085e070100b31b0279")
    event.data = bytearray(b"\nR\x08^\x07\x01\x00\xb3\x1b\x02y")
    await _signal_event(hass, event)
    entity = rfxtrx_core.RFX_DEVICES["sensor_07_01"]["Temperature"]
    assert 2 == len(rfxtrx_core.RFX_DEVICES)
    assert {
        "Humidity status": "normal",
        "Temperature": 17.9,
        "Rssi numeric": 7,
        "Humidity": 27,
        "Battery numeric": 9,
        "Humidity status numeric": 2,
    } == entity.device_state_attributes
    assert "0a520801070100b81b0279" == entity.__str__()

    # trying to add a switch
    event = rfxtrx_core.get_rfx_object("0b1100cd0213c7f210010f70")
    await _signal_event(hass, event)
    assert 2 == len(rfxtrx_core.RFX_DEVICES)


async def test_discover_sensor_noautoadd(hass, rfxtrx):
    """Test with discover of sensor when auto add is False."""
    await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "rfxtrx", "automatic_add": False, "devices": {}}},
    )
    await hass.async_block_till_done()

    event = rfxtrx_core.get_rfx_object("0a520801070100b81b0279")
    event.data = bytearray(b"\nR\x08\x01\x07\x01\x00\xb8\x1b\x02y")

    assert 0 == len(rfxtrx_core.RFX_DEVICES)
    await _signal_event(hass, event)
    assert 0 == len(rfxtrx_core.RFX_DEVICES)

    await _signal_event(hass, event)
    assert 0 == len(rfxtrx_core.RFX_DEVICES)

    event = rfxtrx_core.get_rfx_object("0a52080405020095240279")
    event.data = bytearray(b"\nR\x08\x04\x05\x02\x00\x95$\x02y")
    await _signal_event(hass, event)
    assert 0 == len(rfxtrx_core.RFX_DEVICES)

    event = rfxtrx_core.get_rfx_object("0a52085e070100b31b0279")
    event.data = bytearray(b"\nR\x08^\x07\x01\x00\xb3\x1b\x02y")
    await _signal_event(hass, event)
    assert 0 == len(rfxtrx_core.RFX_DEVICES)


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

    assert 2 == len(rfxtrx_core.RFX_DEVICES)
    device_num = 0
    for id in rfxtrx_core.RFX_DEVICES:
        if id == "sensor_06_01":
            device_num = device_num + 1
            assert len(rfxtrx_core.RFX_DEVICES[id]) == 2
            _entity_temp = rfxtrx_core.RFX_DEVICES[id]["Temperature"]
            _entity_hum = rfxtrx_core.RFX_DEVICES[id]["Humidity"]
            assert UNIT_PERCENTAGE == _entity_hum.unit_of_measurement
            assert "Bath" == _entity_hum.__str__()
            assert _entity_temp.state is None
            assert TEMP_CELSIUS == _entity_temp.unit_of_measurement
            assert "Bath" == _entity_temp.__str__()
        elif id == "sensor_05_02":
            device_num = device_num + 1
            entity = rfxtrx_core.RFX_DEVICES[id]["Temperature"]
            assert entity.state is None
            assert TEMP_CELSIUS == entity.unit_of_measurement
            assert "Test" == entity.__str__()

    assert 2 == device_num

    event = rfxtrx_core.get_rfx_object("0a520802060101ff0f0269")
    event.data = bytearray(b"\nR\x08\x01\x07\x01\x00\xb8\x1b\x02y")
    await _signal_event(hass, event)

    await _signal_event(hass, event)
    event = rfxtrx_core.get_rfx_object("0a52080705020085220269")
    event.data = bytearray(b"\nR\x08\x04\x05\x02\x00\x95$\x02y")
    await _signal_event(hass, event)

    assert 2 == len(rfxtrx_core.RFX_DEVICES)

    device_num = 0
    for id in rfxtrx_core.RFX_DEVICES:
        if id == "sensor_06_01":
            device_num = device_num + 1
            assert len(rfxtrx_core.RFX_DEVICES[id]) == 2
            _entity_temp = rfxtrx_core.RFX_DEVICES[id]["Temperature"]
            _entity_hum = rfxtrx_core.RFX_DEVICES[id]["Humidity"]
            assert UNIT_PERCENTAGE == _entity_hum.unit_of_measurement
            assert 15 == _entity_hum.state
            assert {
                "Battery numeric": 9,
                "Temperature": 51.1,
                "Humidity": 15,
                "Humidity status": "normal",
                "Humidity status numeric": 2,
                "Rssi numeric": 6,
            } == _entity_hum.device_state_attributes
            assert "Bath" == _entity_hum.__str__()

            assert TEMP_CELSIUS == _entity_temp.unit_of_measurement
            assert 51.1 == _entity_temp.state
            assert {
                "Battery numeric": 9,
                "Temperature": 51.1,
                "Humidity": 15,
                "Humidity status": "normal",
                "Humidity status numeric": 2,
                "Rssi numeric": 6,
            } == _entity_temp.device_state_attributes
            assert "Bath" == _entity_temp.__str__()
        elif id == "sensor_05_02":
            device_num = device_num + 1
            entity = rfxtrx_core.RFX_DEVICES[id]["Temperature"]
            assert TEMP_CELSIUS == entity.unit_of_measurement
            assert 13.3 == entity.state
            assert {
                "Humidity status": "normal",
                "Temperature": 13.3,
                "Rssi numeric": 6,
                "Humidity": 34,
                "Battery numeric": 9,
                "Humidity status numeric": 2,
            } == entity.device_state_attributes
            assert "Test" == entity.__str__()

    assert 2 == device_num
    assert 2 == len(rfxtrx_core.RFX_DEVICES)
