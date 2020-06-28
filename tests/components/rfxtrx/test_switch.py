"""The tests for the RFXtrx switch platform."""
import unittest

import RFXtrx as rfxtrxmod
import pytest

from homeassistant.components import rfxtrx as rfxtrx_core
from homeassistant.setup import setup_component

from tests.common import assert_setup_component, get_test_home_assistant, mock_component


@pytest.mark.skipif("os.environ.get('RFXTRX') != 'RUN'")
class TestSwitchRfxtrx(unittest.TestCase):
    """Test the RFXtrx switch platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_component(self.hass, "rfxtrx")
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS.clear()
        rfxtrx_core.RFX_DEVICES.clear()
        if rfxtrx_core.DATA_RFXOBJECT in self.hass.data:
            self.hass.data[rfxtrx_core.DATA_RFXOBJECT].close_connection()
        self.hass.stop()

    def test_valid_config(self):
        """Test configuration."""
        assert setup_component(
            self.hass,
            "switch",
            {
                "switch": {
                    "platform": "rfxtrx",
                    "automatic_add": True,
                    "devices": {
                        "0b1100cd0213c7f210010f51": {
                            "name": "Test",
                            rfxtrx_core.ATTR_FIRE_EVENT: True,
                        }
                    },
                }
            },
        )

    def test_valid_config_int_device_id(self):
        """Test configuration."""
        assert setup_component(
            self.hass,
            "switch",
            {
                "switch": {
                    "platform": "rfxtrx",
                    "automatic_add": True,
                    "devices": {
                        710000141010170: {
                            "name": "Test",
                            rfxtrx_core.ATTR_FIRE_EVENT: True,
                        }
                    },
                }
            },
        )

    def test_invalid_config2(self):
        """Test invalid configuration."""
        with assert_setup_component(0):
            setup_component(
                self.hass,
                "switch",
                {
                    "switch": {
                        "platform": "rfxtrx",
                        "automatic_add": True,
                        "invalid_key": "afda",
                        "devices": {
                            "0b1100cd0213c7f210010f51": {
                                "name": "Test",
                                rfxtrx_core.ATTR_FIRE_EVENT: True,
                            }
                        },
                    }
                },
            )

    def test_default_config(self):
        """Test with 0 switches."""
        assert setup_component(
            self.hass, "switch", {"switch": {"platform": "rfxtrx", "devices": {}}}
        )
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

    def test_one_switch(self):
        """Test with 1 switch."""
        assert setup_component(
            self.hass,
            "switch",
            {
                "switch": {
                    "platform": "rfxtrx",
                    "devices": {"0b1100cd0213c7f210010f51": {"name": "Test"}},
                }
            },
        )

        self.hass.data[rfxtrx_core.DATA_RFXOBJECT] = rfxtrxmod.Core(
            "", transport_protocol=rfxtrxmod.DummyTransport
        )

        assert 1 == len(rfxtrx_core.RFX_DEVICES)
        entity = rfxtrx_core.RFX_DEVICES["213c7f2_16"]
        entity.hass = self.hass
        assert "Test" == entity.name
        assert "off" == entity.state
        assert entity.assumed_state
        assert entity.signal_repetitions == 1
        assert not entity.should_fire_event
        assert not entity.should_poll

        assert not entity.is_on
        entity.turn_on()
        assert entity.is_on
        entity.turn_off()
        assert not entity.is_on

        assert "Test" == entity.name
        assert "off" == entity.state
        entity.turn_on()
        assert "on" == entity.state
        entity.turn_off()
        assert "off" == entity.state

    def test_several_switches(self):
        """Test with 3 switches."""
        assert setup_component(
            self.hass,
            "switch",
            {
                "switch": {
                    "platform": "rfxtrx",
                    "signal_repetitions": 3,
                    "devices": {
                        "0b1100cd0213c7f230010f71": {"name": "Test"},
                        "0b1100100118cdea02010f70": {"name": "Bath"},
                        "0b1100101118cdea02010f70": {"name": "Living"},
                    },
                }
            },
        )

        assert 3 == len(rfxtrx_core.RFX_DEVICES)
        device_num = 0
        for id in rfxtrx_core.RFX_DEVICES:
            entity = rfxtrx_core.RFX_DEVICES[id]
            assert entity.signal_repetitions == 3
            if entity.name == "Living":
                device_num = device_num + 1
                assert "off" == entity.state
                assert "<Entity Living: off>" == entity.__str__()
            elif entity.name == "Bath":
                device_num = device_num + 1
                assert "off" == entity.state
                assert "<Entity Bath: off>" == entity.__str__()
            elif entity.name == "Test":
                device_num = device_num + 1
                assert "off" == entity.state
                assert "<Entity Test: off>" == entity.__str__()

        assert 3 == device_num

    def test_discover_switch(self):
        """Test with discovery of switches."""
        assert setup_component(
            self.hass,
            "switch",
            {"switch": {"platform": "rfxtrx", "automatic_add": True, "devices": {}}},
        )

        event = rfxtrx_core.get_rfx_object("0b1100100118cdea02010f70")
        event.data = bytearray(
            [0x0B, 0x11, 0x00, 0x10, 0x01, 0x18, 0xCD, 0xEA, 0x01, 0x01, 0x0F, 0x70]
        )

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        entity = rfxtrx_core.RFX_DEVICES["118cdea_2"]
        assert 1 == len(rfxtrx_core.RFX_DEVICES)
        assert "<Entity 0b1100100118cdea01010f70: on>" == entity.__str__()

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 1 == len(rfxtrx_core.RFX_DEVICES)

        event = rfxtrx_core.get_rfx_object("0b1100100118cdeb02010f70")
        event.data = bytearray(
            [0x0B, 0x11, 0x00, 0x12, 0x01, 0x18, 0xCD, 0xEA, 0x02, 0x00, 0x00, 0x70]
        )

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        entity = rfxtrx_core.RFX_DEVICES["118cdeb_2"]
        assert 2 == len(rfxtrx_core.RFX_DEVICES)
        assert "<Entity 0b1100120118cdea02000070: on>" == entity.__str__()

        # Trying to add a sensor
        event = rfxtrx_core.get_rfx_object("0a52085e070100b31b0279")
        event.data = bytearray(b"\nR\x08^\x07\x01\x00\xb3\x1b\x02y")
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 2 == len(rfxtrx_core.RFX_DEVICES)

        # Trying to add a light
        event = rfxtrx_core.get_rfx_object("0b1100100118cdea02010f70")
        event.data = bytearray(
            [0x0B, 0x11, 0x11, 0x10, 0x01, 0x18, 0xCD, 0xEA, 0x01, 0x02, 0x0F, 0x70]
        )
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 2 == len(rfxtrx_core.RFX_DEVICES)

        # Trying to add a rollershutter
        event = rfxtrx_core.get_rfx_object("0a1400adf394ab020e0060")
        event.data = bytearray(
            [0x0A, 0x14, 0x00, 0xAD, 0xF3, 0x94, 0xAB, 0x02, 0x0E, 0x00, 0x60]
        )
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 2 == len(rfxtrx_core.RFX_DEVICES)

    def test_discover_switch_noautoadd(self):
        """Test with discovery of switch when auto add is False."""
        assert setup_component(
            self.hass,
            "switch",
            {"switch": {"platform": "rfxtrx", "automatic_add": False, "devices": {}}},
        )

        event = rfxtrx_core.get_rfx_object("0b1100100118cdea02010f70")
        event.data = bytearray(
            [0x0B, 0x11, 0x00, 0x10, 0x01, 0x18, 0xCD, 0xEA, 0x01, 0x01, 0x0F, 0x70]
        )

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        event = rfxtrx_core.get_rfx_object("0b1100100118cdeb02010f70")
        event.data = bytearray(
            [0x0B, 0x11, 0x00, 0x12, 0x01, 0x18, 0xCD, 0xEA, 0x02, 0x00, 0x00, 0x70]
        )
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        # Trying to add a sensor
        event = rfxtrx_core.get_rfx_object("0a52085e070100b31b0279")
        event.data = bytearray(b"\nR\x08^\x07\x01\x00\xb3\x1b\x02y")
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        # Trying to add a light
        event = rfxtrx_core.get_rfx_object("0b1100100118cdea02010f70")
        event.data = bytearray(
            [0x0B, 0x11, 0x11, 0x10, 0x01, 0x18, 0xCD, 0xEA, 0x01, 0x02, 0x0F, 0x70]
        )
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        # Trying to add a rollershutter
        event = rfxtrx_core.get_rfx_object("0a1400adf394ab020e0060")
        event.data = bytearray(
            [0x0A, 0x14, 0x00, 0xAD, 0xF3, 0x94, 0xAB, 0x02, 0x0E, 0x00, 0x60]
        )
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS[0](event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)
