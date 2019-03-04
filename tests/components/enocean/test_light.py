"""Test EnOcean light implementation."""
import unittest
from unittest.mock import MagicMock, patch

from enocean.protocol.packet import Packet

from homeassistant.components import enocean as enocean_component
from homeassistant.components.enocean import light


class TestEnOceanLight(unittest.TestCase):
    """Verify that the light can understand EnOcean packets."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        enocean_component.ENOCEAN_DONGLE = MagicMock()
        self.sender_id = [0xAA, 0xAA, 0xAA, 0xAA]
        self.dev_id = [0xBB, 0xBB, 0xBB, 0xBB]
        self.device = light.EnOceanLight(
            self.sender_id, 'light name', self.dev_id)

    def test_setup(self):
        """Test initialization."""
        assert self.device.name == 'light name'
        assert self.device.is_on is False
        assert self.device.dev_id == self.dev_id

    @patch.object(light.EnOceanLight, 'schedule_update_ha_state')
    def test_eltako_dimmer_telegram(self, mock_update):
        """Test that it can handle an Eltako-specific telegram"""
        data = [0xa5, 0x02, 0x0a, 0]
        data.extend(self.sender_id)
        data.extend([0x00])
        pkg = Packet(0x01, data)
        self.device.value_changed(pkg)
        assert self.device.brightness == 25
        assert self.device.is_on is True
        assert mock_update.call_count == 1
