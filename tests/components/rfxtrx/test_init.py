"""The tests for the Rfxtrx component."""
# pylint: disable=protected-access
import unittest

import pytest

from homeassistant.components import rfxtrx
from homeassistant.core import callback
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


@pytest.mark.skipif("os.environ.get('RFXTRX') != 'RUN'")
class TestRFXTRX(unittest.TestCase):
    """Test the Rfxtrx component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS = []
        rfxtrx.RFX_DEVICES = {}
        if rfxtrx.RFXOBJECT:
            rfxtrx.RFXOBJECT.close_connection()
        self.hass.stop()

    def test_default_config(self):
        """Test configuration."""
        assert setup_component(
            self.hass,
            "rfxtrx",
            {
                "rfxtrx": {
                    "device": "/dev/serial/by-id/usb"
                    + "-RFXCOM_RFXtrx433_A1Y0NJGR-if00-port0",
                    "dummy": True,
                }
            },
        )

        assert setup_component(
            self.hass,
            "sensor",
            {"sensor": {"platform": "rfxtrx", "automatic_add": True, "devices": {}}},
        )

        assert len(rfxtrx.RFXOBJECT.sensors()) == 2

    def test_valid_config(self):
        """Test configuration."""
        assert setup_component(
            self.hass,
            "rfxtrx",
            {
                "rfxtrx": {
                    "device": "/dev/serial/by-id/usb"
                    + "-RFXCOM_RFXtrx433_A1Y0NJGR-if00-port0",
                    "dummy": True,
                }
            },
        )

    def test_valid_config2(self):
        """Test configuration."""
        assert setup_component(
            self.hass,
            "rfxtrx",
            {
                "rfxtrx": {
                    "device": "/dev/serial/by-id/usb"
                    + "-RFXCOM_RFXtrx433_A1Y0NJGR-if00-port0",
                    "dummy": True,
                    "debug": True,
                }
            },
        )

    def test_invalid_config(self):
        """Test configuration."""
        assert not setup_component(self.hass, "rfxtrx", {"rfxtrx": {}})

        assert not setup_component(
            self.hass,
            "rfxtrx",
            {
                "rfxtrx": {
                    "device": "/dev/serial/by-id/usb"
                    + "-RFXCOM_RFXtrx433_A1Y0NJGR-if00-port0",
                    "invalid_key": True,
                }
            },
        )

    def test_fire_event(self):
        """Test fire event."""
        assert setup_component(
            self.hass,
            "rfxtrx",
            {
                "rfxtrx": {
                    "device": "/dev/serial/by-id/usb"
                    + "-RFXCOM_RFXtrx433_A1Y0NJGR-if00-port0",
                    "dummy": True,
                }
            },
        )
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
                            rfxtrx.ATTR_FIREEVENT: True,
                        }
                    },
                }
            },
        )

        calls = []

        @callback
        def record_event(event):
            """Add recorded event to set."""
            calls.append(event)

        self.hass.bus.listen(rfxtrx.EVENT_BUTTON_PRESSED, record_event)
        self.hass.block_till_done()

        entity = rfxtrx.RFX_DEVICES["213c7f216"]
        assert "Test" == entity.name
        assert "off" == entity.state
        assert entity.should_fire_event

        event = rfxtrx.get_rfx_object("0b1100cd0213c7f210010f51")
        event.data = bytearray(
            [0x0B, 0x11, 0x00, 0x10, 0x01, 0x18, 0xCD, 0xEA, 0x01, 0x01, 0x0F, 0x70]
        )
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS[0](event)
        self.hass.block_till_done()

        assert event.values["Command"] == "On"
        assert "on" == entity.state
        assert self.hass.states.get("switch.test").state == "on"
        assert 1 == len(calls)
        assert calls[0].data == {"entity_id": "switch.test", "state": "on"}

    def test_fire_event_sensor(self):
        """Test fire event."""
        assert setup_component(
            self.hass,
            "rfxtrx",
            {
                "rfxtrx": {
                    "device": "/dev/serial/by-id/usb"
                    + "-RFXCOM_RFXtrx433_A1Y0NJGR-if00-port0",
                    "dummy": True,
                }
            },
        )
        assert setup_component(
            self.hass,
            "sensor",
            {
                "sensor": {
                    "platform": "rfxtrx",
                    "automatic_add": True,
                    "devices": {
                        "0a520802060100ff0e0269": {
                            "name": "Test",
                            rfxtrx.ATTR_FIREEVENT: True,
                        }
                    },
                }
            },
        )

        calls = []

        @callback
        def record_event(event):
            """Add recorded event to set."""
            calls.append(event)

        self.hass.bus.listen("signal_received", record_event)
        self.hass.block_till_done()
        event = rfxtrx.get_rfx_object("0a520802060101ff0f0269")
        event.data = bytearray(b"\nR\x08\x01\x07\x01\x00\xb8\x1b\x02y")
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS[0](event)

        self.hass.block_till_done()
        assert 1 == len(calls)
        assert calls[0].data == {"entity_id": "sensor.test"}
