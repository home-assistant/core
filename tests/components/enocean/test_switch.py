"""Test EnOcean light implementation."""
import unittest
from unittest.mock import MagicMock, patch

from enocean.protocol.packet import RadioPacket

from homeassistant.components import enocean as enocean_component
from homeassistant.components.enocean import switch


class TestEnOceanSwitch(unittest.TestCase):
    """Verify that the switch can understand EnOcean packets."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        enocean_component.ENOCEAN_DONGLE = MagicMock()
        self.channel = 1
        self.dev_id = [0xBB, 0xBB, 0xBB, 0xBB]
        self.device = switch.EnOceanSwitch(
            self.dev_id, 'light name', self.channel)

    def test_setup(self):
        """Test sensor initialization."""
        assert self.device.name == 'light name'
        assert self.device.is_on is False

    @patch.object(switch.EnOceanSwitch, 'schedule_update_ha_state')
    def test_actuator_status_telegram(self, mock_update):
        """Test that it can handle an d2_01_09 Actuator Status Response."""
        pkg = RadioPacket.create(rorg=0xD2, rorg_func=0x01, rorg_type=0x01,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA], command=4,
                                 destination=[0xFF, 0xFF, 0xFF, 0xFF],
                                 OV=50, IO=self.channel, PF=1, PFD=1, EL=0)
        self.device.value_changed(pkg)
        assert self.device.is_on is True
        assert mock_update.call_count == 1

    @patch.object(switch.EnOceanSwitch, 'schedule_update_ha_state')
    def test_power_meter_telegram(self, mock_update):
        """Test that it can handle an A5-12-01 Power Meter Reading."""

        # anything below 10W is ignored
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x12, rorg_type=0x01,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA],
                                 destination=[0xFF, 0xFF, 0xFF, 0xFF],
                                 MR=1, DT=1, DIV=0)
        self.device.value_changed(pkg)
        assert self.device.is_on is False

        # anything >= 10W is considered to be "on"
        pkg = RadioPacket.create(rorg=0xA5, rorg_func=0x12, rorg_type=0x01,
                                 sender=[0xAA, 0xAA, 0xAA, 0xAA],
                                 destination=[0xFF, 0xFF, 0xFF, 0xFF],
                                 MR=15, DT=1, DIV=0)
        self.device.value_changed(pkg)
        assert self.device.is_on is True
        assert mock_update.call_count == 2
