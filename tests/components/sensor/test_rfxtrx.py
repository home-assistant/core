"""The tests for the Rfxtrx sensor platform."""
import unittest


from homeassistant.components.sensor import rfxtrx
from homeassistant.components import rfxtrx as rfxtrx_core
from homeassistant.const import TEMP_CELCIUS

from tests.common import get_test_home_assistant


class TestSensorRfxtrx(unittest.TestCase):
    """Test the Rfxtrx sensor platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant(0)

    def tearDown(self):
        """Stop everything that was started."""
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS = []
        rfxtrx_core.RFX_DEVICES = {}
        self.hass.stop()

    def test_default_config(self):
        """Test with 0 sensor."""
        config = {'devices': {}}
        devices = []

        def add_dev_callback(devs):
            """Add a callback to add devices."""
            for dev in devs:
                devices.append(dev)

        rfxtrx.setup_platform(self.hass, config, add_dev_callback)
        self.assertEqual(0, len(devices))

    def test_one_sensor(self):
        """Test with 1 sensor."""
        config = {'devices':
                  {'sensor_0502': {
                      'name': 'Test',
                      'packetid': '0a52080705020095220269',
                      'data_type': 'Temperature'}}}
        devices = []

        def add_dev_callback(devs):
            """Add a callback to add devices."""
            for dev in devs:
                devices.append(dev)

        rfxtrx.setup_platform(self.hass, config, add_dev_callback)

        self.assertEqual(1, len(devices))
        entity = devices[0]
        self.assertEqual('Test', entity.name)
        self.assertEqual(TEMP_CELCIUS, entity.unit_of_measurement)
        self.assertEqual(14.9, entity.state)
        self.assertEqual({'Humidity status': 'normal', 'Temperature': 14.9,
                          'Rssi numeric': 6, 'Humidity': 34,
                          'Battery numeric': 9,
                          'Humidity status numeric': 2},
                         entity.device_state_attributes)

    def test_several_sensors(self):
        """Test with 3 sensors."""
        config = {'devices':
                  {'sensor_0502': {
                      'name': 'Test',
                      'packetid': '0a52080705020095220269',
                      'data_type': 'Temperature'},
                   'sensor_0601': {
                       'name': 'Bath_Humidity',
                       'packetid': '0a520802060100ff0e0269',
                       'data_type': 'Humidity'},
                   'sensor_0601 2': {
                       'name': 'Bath',
                       'packetid': '0a520802060100ff0e0269'}}}
        devices = []

        def add_dev_callback(devs):
            """Add a callback to add devices."""
            for dev in devs:
                devices.append(dev)

        rfxtrx.setup_platform(self.hass, config, add_dev_callback)

        self.assertEqual(3, len(devices))
        device_num = 0
        for entity in devices:
            if entity.name == 'Bath_Humidity':
                device_num = device_num + 1
                self.assertEqual('%', entity.unit_of_measurement)
                self.assertEqual(14, entity.state)
                self.assertEqual({'Battery numeric': 9, 'Temperature': 25.5,
                                  'Humidity': 14, 'Humidity status': 'normal',
                                  'Humidity status numeric': 2,
                                  'Rssi numeric': 6},
                                 entity.device_state_attributes)
                self.assertEqual('Bath_Humidity', entity.__str__())
            elif entity.name == 'Bath':
                device_num = device_num + 1
                self.assertEqual(TEMP_CELCIUS, entity.unit_of_measurement)
                self.assertEqual(25.5, entity.state)
                self.assertEqual({'Battery numeric': 9, 'Temperature': 25.5,
                                  'Humidity': 14, 'Humidity status': 'normal',
                                  'Humidity status numeric': 2,
                                  'Rssi numeric': 6},
                                 entity.device_state_attributes)
                self.assertEqual('Bath', entity.__str__())
            elif entity.name == 'Test':
                device_num = device_num + 1
                self.assertEqual(TEMP_CELCIUS, entity.unit_of_measurement)
                self.assertEqual(14.9, entity.state)
                self.assertEqual({'Humidity status': 'normal',
                                  'Temperature': 14.9,
                                  'Rssi numeric': 6, 'Humidity': 34,
                                  'Battery numeric': 9,
                                  'Humidity status numeric': 2},
                                 entity.device_state_attributes)
                self.assertEqual('Test', entity.__str__())

        self.assertEqual(3, device_num)

    def test_discover_sensor(self):
        """Test with discovery of sensor."""
        config = {'devices': {}}
        devices = []

        def add_dev_callback(devs):
            """Add a callback to add devices."""
            for dev in devs:
                devices.append(dev)

        rfxtrx.setup_platform(self.hass, config, add_dev_callback)
        event = rfxtrx_core.get_rfx_object('0a520801070100b81b0279')
        event.data = bytearray(b'\nR\x08\x01\x07\x01\x00\xb8\x1b\x02y')
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)

        entity = devices[0]
        self.assertEqual(1, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(1, len(devices))
        self.assertEqual({'Humidity status': 'normal',
                          'Temperature': 18.4,
                          'Rssi numeric': 7, 'Humidity': 27,
                          'Battery numeric': 9,
                          'Humidity status numeric': 2},
                         entity.device_state_attributes)
        self.assertEqual('sensor_0701 : 0a520801070100b81b0279',
                         entity.__str__())

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.assertEqual(1, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(1, len(devices))

        event = rfxtrx_core.get_rfx_object('0a52080405020095240279')
        event.data = bytearray(b'\nR\x08\x04\x05\x02\x00\x95$\x02y')
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        entity = devices[1]
        self.assertEqual(2, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(2, len(devices))
        self.assertEqual({'Humidity status': 'normal',
                          'Temperature': 14.9,
                          'Rssi numeric': 7, 'Humidity': 36,
                          'Battery numeric': 9,
                          'Humidity status numeric': 2},
                         entity.device_state_attributes)
        self.assertEqual('sensor_0502 : 0a52080405020095240279',
                         entity.__str__())

        event = rfxtrx_core.get_rfx_object('0a52085e070100b31b0279')
        event.data = bytearray(b'\nR\x08^\x07\x01\x00\xb3\x1b\x02y')
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        entity = devices[0]
        self.assertEqual(2, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(2, len(devices))
        self.assertEqual({'Humidity status': 'normal',
                          'Temperature': 17.9,
                          'Rssi numeric': 7, 'Humidity': 27,
                          'Battery numeric': 9,
                          'Humidity status numeric': 2},
                         entity.device_state_attributes)
        self.assertEqual('sensor_0701 : 0a520801070100b81b0279',
                         entity.__str__())

        # trying to add a switch
        event = rfxtrx_core.get_rfx_object('0b1100cd0213c7f210010f70')
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.assertEqual(2, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(2, len(devices))

    def test_discover_sensor_noautoadd(self):
        """Test with discover of sensor when auto add is False."""
        config = {'automatic_add': False, 'devices': {}}
        devices = []

        def add_dev_callback(devs):
            """Add a callback to add devices."""
            for dev in devs:
                devices.append(dev)

        rfxtrx.setup_platform(self.hass, config, add_dev_callback)
        event = rfxtrx_core.get_rfx_object('0a520801070100b81b0279')
        event.data = bytearray(b'\nR\x08\x01\x07\x01\x00\xb8\x1b\x02y')

        self.assertEqual(0, len(rfxtrx_core.RFX_DEVICES))
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.assertEqual(0, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(0, len(devices))

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.assertEqual(0, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(0, len(devices))

        event = rfxtrx_core.get_rfx_object('0a52080405020095240279')
        event.data = bytearray(b'\nR\x08\x04\x05\x02\x00\x95$\x02y')
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.assertEqual(0, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(0, len(devices))

        event = rfxtrx_core.get_rfx_object('0a52085e070100b31b0279')
        event.data = bytearray(b'\nR\x08^\x07\x01\x00\xb3\x1b\x02y')
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.assertEqual(0, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(0, len(devices))
