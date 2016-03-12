"""The tests for the Rfxtrx switch platform."""
import unittest

from homeassistant.components import rfxtrx as rfxtrx_core
from homeassistant.components.switch import rfxtrx
from unittest.mock import patch

import pytest

from tests.common import get_test_home_assistant


@pytest.mark.skipif(True, reason='Does not clean up properly, takes 100% CPU')
class TestSwitchRfxtrx(unittest.TestCase):
    """Test the Rfxtrx switch platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant(0)

    def tearDown(self):
        """Stop everything that was started."""
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS = []
        rfxtrx_core.RFX_DEVICES = {}
        self.hass.stop()

    def test_default_config(self):
        """Test with 0 switches."""
        config = {'devices': {}}
        devices = []

        def add_dev_callback(devs):
            """Add a callback to add devices."""
            for dev in devs:
                devices.append(dev)

        rfxtrx.setup_platform(self.hass, config, add_dev_callback)
        self.assertEqual(0, len(devices))

    def test_one_sensor(self):
        """Test with 1 switch."""
        config = {'devices':
                  {'123efab1': {
                      'name': 'Test',
                      'packetid': '0b1100cd0213c7f210010f51'}}}
        import RFXtrx as rfxtrxmod
        rfxtrx_core.RFXOBJECT =\
            rfxtrxmod.Core("", transport_protocol=rfxtrxmod.DummyTransport)

        devices = []

        def add_dev_callback(devs):
            """Add a callback to add devices."""
            for dev in devs:
                devices.append(dev)

        rfxtrx.setup_platform(self.hass, config, add_dev_callback)

        self.assertEqual(1, len(devices))
        entity = devices[0]
        self.assertEqual('Test', entity.name)
        self.assertEqual('off', entity.state)
        self.assertTrue(entity.assumed_state)
        self.assertEqual(entity.signal_repetitions, 1)
        self.assertFalse(entity.should_fire_event)
        self.assertFalse(entity.should_poll)

        self.assertFalse(entity.is_on)
        with patch('homeassistant.components.switch.' +
                   'rfxtrx.RfxtrxSwitch.update_ha_state',
                   return_value=None):
            entity.turn_on()
        self.assertTrue(entity.is_on)
        with patch('homeassistant.components.switch.' +
                   'rfxtrx.RfxtrxSwitch.update_ha_state',
                   return_value=None):
            entity.turn_off()
        self.assertFalse(entity.is_on)

    def test_several_switchs(self):
        """Test with 3 switches."""
        config = {'signal_repetitions': 3,
                  'devices':
                  {'123efab1': {
                      'name': 'Test',
                      'packetid': '0b1100cd0213c7f230010f71'},
                   '118cdea2': {
                       'name': 'Bath',
                       'packetid': '0b1100100118cdea02010f70'},
                   '213c7f216': {
                       'name': 'Living',
                       'packetid': '2b1121cd1213c7f211111f71'}}}
        devices = []

        def add_dev_callback(devs):
            """Add a callback to add devices."""
            for dev in devs:
                devices.append(dev)

        rfxtrx.setup_platform(self.hass, config, add_dev_callback)

        self.assertEqual(3, len(devices))
        device_num = 0
        for entity in devices:
            self.assertEqual(entity.signal_repetitions, 3)
            if entity.name == 'Living':
                device_num = device_num + 1
                self.assertEqual('off', entity.state)
                self.assertEqual('<Entity Living: off>', entity.__str__())
            elif entity.name == 'Bath':
                device_num = device_num + 1
                self.assertEqual('off', entity.state)
                self.assertEqual('<Entity Bath: off>', entity.__str__())
            elif entity.name == 'Test':
                device_num = device_num + 1
                self.assertEqual('off', entity.state)
                self.assertEqual('<Entity Test: off>', entity.__str__())

        self.assertEqual(3, device_num)

    def test_discover_switch(self):
        """Test with discovery of switches."""
        config = {'automatic_add': True, 'devices': {}}
        devices = []

        def add_dev_callback(devs):
            """Add a callback to add devices."""
            for dev in devs:
                devices.append(dev)

        rfxtrx.setup_platform(self.hass, config, add_dev_callback)

        event = rfxtrx_core.get_rfx_object('0b1100100118cdea02010f70')
        event.data = bytearray([0x0b, 0x11, 0x00, 0x10, 0x01, 0x18,
                                0xcd, 0xea, 0x01, 0x01, 0x0f, 0x70])
        with patch('homeassistant.components.switch.' +
                   'rfxtrx.RfxtrxSwitch.update_ha_state',
                   return_value=None):
            rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        entity = devices[0]
        self.assertEqual(1, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(1, len(devices))
        self.assertEqual('<Entity 118cdea2 : 0b1100100118cdea01010f70: on>',
                         entity.__str__())

        with patch('homeassistant.components.switch.' +
                   'rfxtrx.RfxtrxSwitch.update_ha_state',
                   return_value=None):
            rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.assertEqual(1, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(1, len(devices))

        event = rfxtrx_core.get_rfx_object('0b1100100118cdeb02010f70')
        event.data = bytearray([0x0b, 0x11, 0x00, 0x12, 0x01, 0x18,
                                0xcd, 0xea, 0x02, 0x00, 0x00, 0x70])
        with patch('homeassistant.components.switch.' +
                   'rfxtrx.RfxtrxSwitch.update_ha_state',
                   return_value=None):
            rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        entity = devices[1]
        self.assertEqual(2, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(2, len(devices))
        self.assertEqual('<Entity 118cdeb2 : 0b1100120118cdea02000070: on>',
                         entity.__str__())

        # Trying to add a sensor
        event = rfxtrx_core.get_rfx_object('0a52085e070100b31b0279')
        event.data = bytearray(b'\nR\x08^\x07\x01\x00\xb3\x1b\x02y')
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.assertEqual(2, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(2, len(devices))

        # Trying to add a light
        event = rfxtrx_core.get_rfx_object('0b1100100118cdea02010f70')
        event.data = bytearray([0x0b, 0x11, 0x11, 0x10, 0x01, 0x18,
                                0xcd, 0xea, 0x01, 0x02, 0x0f, 0x70])
        with patch('homeassistant.components.switch.' +
                   'rfxtrx.RfxtrxSwitch.update_ha_state',
                   return_value=None):
            rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.assertEqual(2, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(2, len(devices))

    def test_discover_switch_noautoadd(self):
        """Test with discovery of switch when auto add is False."""
        config = {'automatic_add': False, 'devices': {}}
        devices = []

        def add_dev_callback(devs):
            """Add a callback to add devices."""
            for dev in devs:
                devices.append(dev)

        rfxtrx.setup_platform(self.hass, config, add_dev_callback)

        event = rfxtrx_core.get_rfx_object('0b1100100118cdea02010f70')
        event.data = bytearray([0x0b, 0x11, 0x00, 0x10, 0x01, 0x18,
                                0xcd, 0xea, 0x01, 0x01, 0x0f, 0x70])
        with patch('homeassistant.components.switch.' +
                   'rfxtrx.RfxtrxSwitch.update_ha_state',
                   return_value=None):
            rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.assertEqual(0, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(0, len(devices))

        with patch('homeassistant.components.switch.' +
                   'rfxtrx.RfxtrxSwitch.update_ha_state',
                   return_value=None):
            rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.assertEqual(0, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(0, len(devices))

        event = rfxtrx_core.get_rfx_object('0b1100100118cdeb02010f70')
        event.data = bytearray([0x0b, 0x11, 0x00, 0x12, 0x01, 0x18,
                                0xcd, 0xea, 0x02, 0x00, 0x00, 0x70])
        with patch('homeassistant.components.switch.' +
                   'rfxtrx.RfxtrxSwitch.update_ha_state',
                   return_value=None):
            rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.assertEqual(0, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(0, len(devices))

        # Trying to add a sensor
        event = rfxtrx_core.get_rfx_object('0a52085e070100b31b0279')
        event.data = bytearray(b'\nR\x08^\x07\x01\x00\xb3\x1b\x02y')
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.assertEqual(0, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(0, len(devices))

        # Trying to add a light
        event = rfxtrx_core.get_rfx_object('0b1100100118cdea02010f70')
        event.data = bytearray([0x0b, 0x11, 0x11, 0x10, 0x01,
                                0x18, 0xcd, 0xea, 0x01, 0x02, 0x0f, 0x70])
        with patch('homeassistant.components.switch.' +
                   'rfxtrx.RfxtrxSwitch.update_ha_state',
                   return_value=None):
            rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.assertEqual(0, len(rfxtrx_core.RFX_DEVICES))
        self.assertEqual(0, len(devices))
