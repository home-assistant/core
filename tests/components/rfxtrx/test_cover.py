"""The tests for the Rfxtrx cover platform."""
import unittest

import RFXtrx as rfxtrxmod
import pytest

from homeassistant.components import rfxtrx as rfxtrx_core
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, mock_component


@pytest.mark.skipif("os.environ.get('RFXTRX') != 'RUN'")
class TestCoverRfxtrx(unittest.TestCase):
    """Test the Rfxtrx cover platform."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_component("rfxtrx")
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS = []
        rfxtrx_core.RFX_DEVICES = {}
        if rfxtrx_core.RFXOBJECT:
            rfxtrx_core.RFXOBJECT.close_connection()
        self.hass.stop()

    def test_valid_config(self):
        """Test configuration."""
        assert setup_component(
            self.hass,
            "cover",
            {
                "cover": {
                    "platform": "rfxtrx",
                    "automatic_add": True,
                    "devices": {
                        "0b1100cd0213c7f210010f51": {
                            "name": "Test",
                            rfxtrx_core.ATTR_FIREEVENT: True,
                        }
                    },
                }
            },
        )

    def test_invalid_config_capital_letters(self):
        """Test configuration."""
        assert not setup_component(
            self.hass,
            "cover",
            {
                "cover": {
                    "platform": "rfxtrx",
                    "automatic_add": True,
                    "devices": {
                        "2FF7f216": {
                            "name": "Test",
                            "packetid": "0b1100cd0213c7f210010f51",
                            "signal_repetitions": 3,
                        }
                    },
                }
            },
        )

    def test_invalid_config_extra_key(self):
        """Test configuration."""
        assert not setup_component(
            self.hass,
            "cover",
            {
                "cover": {
                    "platform": "rfxtrx",
                    "automatic_add": True,
                    "invalid_key": "afda",
                    "devices": {
                        "213c7f216": {
                            "name": "Test",
                            "packetid": "0b1100cd0213c7f210010f51",
                            rfxtrx_core.ATTR_FIREEVENT: True,
                        }
                    },
                }
            },
        )

    def test_invalid_config_capital_packetid(self):
        """Test configuration."""
        assert not setup_component(
            self.hass,
            "cover",
            {
                "cover": {
                    "platform": "rfxtrx",
                    "automatic_add": True,
                    "devices": {
                        "213c7f216": {
                            "name": "Test",
                            "packetid": "AA1100cd0213c7f210010f51",
                            rfxtrx_core.ATTR_FIREEVENT: True,
                        }
                    },
                }
            },
        )

    def test_invalid_config_missing_packetid(self):
        """Test configuration."""
        assert not setup_component(
            self.hass,
            "cover",
            {
                "cover": {
                    "platform": "rfxtrx",
                    "automatic_add": True,
                    "devices": {
                        "213c7f216": {"name": "Test", rfxtrx_core.ATTR_FIREEVENT: True}
                    },
                }
            },
        )

    def test_default_config(self):
        """Test with 0 cover."""
        assert setup_component(
            self.hass, "cover", {"cover": {"platform": "rfxtrx", "devices": {}}}
        )
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

    def test_one_cover(self):
        """Test with 1 cover."""
        assert setup_component(
            self.hass,
            "cover",
            {
                "cover": {
                    "platform": "rfxtrx",
                    "devices": {"0b1400cd0213c7f210010f51": {"name": "Test"}},
                }
            },
        )

        rfxtrx_core.RFXOBJECT = rfxtrxmod.Core(
            "", transport_protocol=rfxtrxmod.DummyTransport
        )

        assert 1 == len(rfxtrx_core.RFX_DEVICES)
        for id in rfxtrx_core.RFX_DEVICES:
            entity = rfxtrx_core.RFX_DEVICES[id]
            assert entity.signal_repetitions == 1
            assert not entity.should_fire_event
            assert not entity.should_poll
            entity.open_cover()
            entity.close_cover()
            entity.stop_cover()

    def test_several_covers(self):
        """Test with 3 covers."""
        assert setup_component(
            self.hass,
            "cover",
            {
                "cover": {
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
            elif entity.name == "Bath":
                device_num = device_num + 1
            elif entity.name == "Test":
                device_num = device_num + 1

        assert 3 == device_num

    def test_discover_covers(self):
        """Test with discovery of covers."""
        assert setup_component(
            self.hass,
            "cover",
            {"cover": {"platform": "rfxtrx", "automatic_add": True, "devices": {}}},
        )

        event = rfxtrx_core.get_rfx_object("0a140002f38cae010f0070")
        event.data = bytearray(
            [0x0A, 0x14, 0x00, 0x02, 0xF3, 0x8C, 0xAE, 0x01, 0x0F, 0x00, 0x70]
        )

        for evt_sub in rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS:
            evt_sub(event)
        assert 1 == len(rfxtrx_core.RFX_DEVICES)

        event = rfxtrx_core.get_rfx_object("0a1400adf394ab020e0060")
        event.data = bytearray(
            [0x0A, 0x14, 0x00, 0xAD, 0xF3, 0x94, 0xAB, 0x02, 0x0E, 0x00, 0x60]
        )

        for evt_sub in rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS:
            evt_sub(event)
        assert 2 == len(rfxtrx_core.RFX_DEVICES)

        # Trying to add a sensor
        event = rfxtrx_core.get_rfx_object("0a52085e070100b31b0279")
        event.data = bytearray(b"\nR\x08^\x07\x01\x00\xb3\x1b\x02y")
        for evt_sub in rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS:
            evt_sub(event)
        assert 2 == len(rfxtrx_core.RFX_DEVICES)

        # Trying to add a light
        event = rfxtrx_core.get_rfx_object("0b1100100118cdea02010f70")
        event.data = bytearray(
            [0x0B, 0x11, 0x11, 0x10, 0x01, 0x18, 0xCD, 0xEA, 0x01, 0x02, 0x0F, 0x70]
        )
        for evt_sub in rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS:
            evt_sub(event)
        assert 2 == len(rfxtrx_core.RFX_DEVICES)

    def test_discover_cover_noautoadd(self):
        """Test with discovery of cover when auto add is False."""
        assert setup_component(
            self.hass,
            "cover",
            {"cover": {"platform": "rfxtrx", "automatic_add": False, "devices": {}}},
        )

        event = rfxtrx_core.get_rfx_object("0a1400adf394ab010d0060")
        event.data = bytearray(
            [0x0A, 0x14, 0x00, 0xAD, 0xF3, 0x94, 0xAB, 0x01, 0x0D, 0x00, 0x60]
        )

        for evt_sub in rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS:
            evt_sub(event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        event = rfxtrx_core.get_rfx_object("0a1400adf394ab020e0060")
        event.data = bytearray(
            [0x0A, 0x14, 0x00, 0xAD, 0xF3, 0x94, 0xAB, 0x02, 0x0E, 0x00, 0x60]
        )
        for evt_sub in rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS:
            evt_sub(event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        # Trying to add a sensor
        event = rfxtrx_core.get_rfx_object("0a52085e070100b31b0279")
        event.data = bytearray(b"\nR\x08^\x07\x01\x00\xb3\x1b\x02y")
        for evt_sub in rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS:
            evt_sub(event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)

        # Trying to add a light
        event = rfxtrx_core.get_rfx_object("0b1100100118cdea02010f70")
        event.data = bytearray(
            [0x0B, 0x11, 0x11, 0x10, 0x01, 0x18, 0xCD, 0xEA, 0x01, 0x02, 0x0F, 0x70]
        )
        for evt_sub in rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS:
            evt_sub(event)
        assert 0 == len(rfxtrx_core.RFX_DEVICES)
