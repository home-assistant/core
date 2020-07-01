"""The tests for the Rfxtrx sensor platform."""
import unittest

import pytest

from homeassistant.components import rfxtrx as rfxtrx_core
from homeassistant.const import TEMP_CELSIUS, UNIT_PERCENTAGE
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, mock_component


@pytest.mark.skipif("os.environ.get('RFXTRX') != 'RUN'")
class TestSensorRfxtrx(unittest.TestCase):
    """Test the Rfxtrx sensor platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_component(self.hass, "rfxtrx")
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS = []
        rfxtrx_core.RFX_DEVICES = {}
        if rfxtrx_core.RFXOBJECT:
            rfxtrx_core.RFXOBJECT.close_connection()
        self.hass.stop()

    def test_default_config(self):
        """Test with 0 sensor."""
        assert setup_component(
            self.hass, "sensor", {"sensor": {"platform": "rfxtrx", "devices": {}}}
        )
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

    def test_old_config_sensor(self):
        """Test with 1 sensor."""
        assert setup_component(
            self.hass,
            "sensor",
            {
                "sensor": {
                    "platform": "rfxtrx",
                    "devices": {
                        "sensor_0502": {
                            "name": "Test",
                            "packetid": "0a52080705020095220269",
                            "data_type": "Temperature",
                        }
                    },
                }
            },
        )

        assert 1 == len(rfxtrx_core.RFX_DEVICES)
        entity = rfxtrx_core.RFX_DEVICES["sensor_0502"]["Temperature"]
        assert "Test" == entity.name
        assert TEMP_CELSIUS == entity.unit_of_measurement
        assert entity.state is None

    def test_one_sensor(self):
        """Test with 1 sensor."""
        assert setup_component(
            self.hass,
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

        assert 1 == len(rfxtrx_core.RFX_DEVICES)
        entity = rfxtrx_core.RFX_DEVICES["sensor_0502"]["Temperature"]
        assert "Test" == entity.name
        assert TEMP_CELSIUS == entity.unit_of_measurement
        assert entity.state is None

    def test_one_sensor_no_datatype(self):
        """Test with 1 sensor."""
        assert setup_component(
            self.hass,
            "sensor",
            {
                "sensor": {
                    "platform": "rfxtrx",
                    "devices": {"0a52080705020095220269": {"name": "Test"}},
                }
            },
        )

        assert 1 == len(rfxtrx_core.RFX_DEVICES)
        entity = rfxtrx_core.RFX_DEVICES["sensor_0502"]["Temperature"]
        assert "Test" == entity.name
        assert TEMP_CELSIUS == entity.unit_of_measurement
        assert entity.state is None

        entity_id = rfxtrx_core.RFX_DEVICES["sensor_0502"]["Temperature"].entity_id
        entity = self.hass.states.get(entity_id)
        assert "Test" == entity.name
        assert "unknown" == entity.state

    def test_several_sensors(self):
        """Test with 3 sensors."""
        assert setup_component(
            self.hass,
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

        assert 2 == len(rfxtrx_core.RFX_DEVICES)
        device_num = 0
        for id in rfxtrx_core.RFX_DEVICES:
            if id == "sensor_0601":
                device_num = device_num + 1
                assert len(rfxtrx_core.RFX_DEVICES[id]) == 2
                _entity_temp = rfxtrx_core.RFX_DEVICES[id]["Temperature"]
                _entity_hum = rfxtrx_core.RFX_DEVICES[id]["Humidity"]
                assert UNIT_PERCENTAGE == _entity_hum.unit_of_measurement
                assert "Bath" == _entity_hum.__str__()
                assert _entity_hum.state is None
                assert TEMP_CELSIUS == _entity_temp.unit_of_measurement
                assert "Bath" == _entity_temp.__str__()
            elif id == "sensor_0502":
                device_num = device_num + 1
                entity = rfxtrx_core.RFX_DEVICES[id]["Temperature"]
                assert entity.state is None
                assert TEMP_CELSIUS == entity.unit_of_measurement
                assert "Test" == entity.__str__()

        assert 2 == device_num

    def test_discover_sensor(self):
        """Test with discovery of sensor."""
        assert setup_component(
            self.hass,
            "sensor",
            {"sensor": {"platform": "rfxtrx", "automatic_add": True, "devices": {}}},
        )

        event = rfxtrx_core.get_rfx_object("0a520801070100b81b0279")
        event.data = bytearray(b"\nR\x08\x01\x07\x01\x00\xb8\x1b\x02y")
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)

        entity = rfxtrx_core.RFX_DEVICES["sensor_0701"]["Temperature"]
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

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 1 == len(rfxtrx_core.RFX_DEVICES)

        event = rfxtrx_core.get_rfx_object("0a52080405020095240279")
        event.data = bytearray(b"\nR\x08\x04\x05\x02\x00\x95$\x02y")
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        entity = rfxtrx_core.RFX_DEVICES["sensor_0502"]["Temperature"]
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
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        entity = rfxtrx_core.RFX_DEVICES["sensor_0701"]["Temperature"]
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
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 2 == len(rfxtrx_core.RFX_DEVICES)

    def test_discover_sensor_noautoadd(self):
        """Test with discover of sensor when auto add is False."""
        assert setup_component(
            self.hass,
            "sensor",
            {"sensor": {"platform": "rfxtrx", "automatic_add": False, "devices": {}}},
        )

        event = rfxtrx_core.get_rfx_object("0a520801070100b81b0279")
        event.data = bytearray(b"\nR\x08\x01\x07\x01\x00\xb8\x1b\x02y")

        assert 0 == len(rfxtrx_core.RFX_DEVICES)
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        event = rfxtrx_core.get_rfx_object("0a52080405020095240279")
        event.data = bytearray(b"\nR\x08\x04\x05\x02\x00\x95$\x02y")
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        event = rfxtrx_core.get_rfx_object("0a52085e070100b31b0279")
        event.data = bytearray(b"\nR\x08^\x07\x01\x00\xb3\x1b\x02y")
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

    def test_update_of_sensors(self):
        """Test with 3 sensors."""
        assert setup_component(
            self.hass,
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

        assert 2 == len(rfxtrx_core.RFX_DEVICES)
        device_num = 0
        for id in rfxtrx_core.RFX_DEVICES:
            if id == "sensor_0601":
                device_num = device_num + 1
                assert len(rfxtrx_core.RFX_DEVICES[id]) == 2
                _entity_temp = rfxtrx_core.RFX_DEVICES[id]["Temperature"]
                _entity_hum = rfxtrx_core.RFX_DEVICES[id]["Humidity"]
                assert UNIT_PERCENTAGE == _entity_hum.unit_of_measurement
                assert "Bath" == _entity_hum.__str__()
                assert _entity_temp.state is None
                assert TEMP_CELSIUS == _entity_temp.unit_of_measurement
                assert "Bath" == _entity_temp.__str__()
            elif id == "sensor_0502":
                device_num = device_num + 1
                entity = rfxtrx_core.RFX_DEVICES[id]["Temperature"]
                assert entity.state is None
                assert TEMP_CELSIUS == entity.unit_of_measurement
                assert "Test" == entity.__str__()

        assert 2 == device_num

        event = rfxtrx_core.get_rfx_object("0a520802060101ff0f0269")
        event.data = bytearray(b"\nR\x08\x01\x07\x01\x00\xb8\x1b\x02y")
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        event = rfxtrx_core.get_rfx_object("0a52080705020085220269")
        event.data = bytearray(b"\nR\x08\x04\x05\x02\x00\x95$\x02y")
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)

        assert 2 == len(rfxtrx_core.RFX_DEVICES)

        device_num = 0
        for id in rfxtrx_core.RFX_DEVICES:
            if id == "sensor_0601":
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
            elif id == "sensor_0502":
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
