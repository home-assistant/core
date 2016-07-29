"""The tests for the Demo Media player platform."""
import unittest
import soco.snapshot
from unittest import mock
import soco

from homeassistant.components.media_player import sonos

from tests.common import get_test_home_assistant

ENTITY_ID = 'media_player.kitchen'


class socoDiscoverMock():
    """Mock class for the soco.discover method"""
    def discover(interface_addr):
        """Returns tuple of soco.SoCo objects representing found speakers"""
        return {SoCoMock('192.0.2.1')}


class SoCoMock():
    """Mock class for the soco.SoCo object"""
    def __init__(self, ip):
        self.ip_address = ip
        self.is_visible = True

    def get_speaker_info(self):
        """Returns a dict with various data points about the speaker"""
        return {'serial_number': 'B8-E9-37-BO-OC-BA:2',
                'software_version': '32.11-30071',
                'uid': 'RINCON_B8E937BOOCBA02500',
                'zone_icon': 'x-rincon-roomicon:kitchen',
                'mac_address': 'B8:E9:37:BO:OC:BA',
                'zone_name': 'Kitchen',
                'hardware_version': '1.8.1.2-1'}

    def get_current_transport_info(self):
        """Returns a dict with the current state of the speaker"""
        return {'current_transport_speed': '1',
                'current_transport_state': 'STOPPED',
                'current_transport_status': 'OK'}

    def get_current_track_info(self):
        """Returns a dict with the current track information"""
        return {'album': '',
                'uri': '',
                'title': '',
                'artist': '',
                'duration': '0:00:00',
                'album_art': '',
                'position': '0:00:00',
                'playlist_position': '0',
                'metadata': ''}

    def is_coordinator(self):
        """Returns true if coordinator"""
        return True

    def partymode(self):
        """Causes the speaker to join all other speakers in the network"""
        return

    def unjoin(self):
        """Causes the speaker to separate itself from other speakers"""
        return


class TestSonosMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        def monkey_available(self):
            return True

        # Monkey patches
        self.real_available = sonos.SonosDevice.available
        sonos.SonosDevice.available = monkey_available

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        # Monkey patches
        sonos.SonosDevice.available = self.real_available
        sonos.DEVICES = []
        self.hass.stop()

    @mock.patch('soco.SoCo', new=SoCoMock)
    def test_ensure_setup_discovery(self):
        """Test a single device using the autodiscovery provided by HASS."""
        sonos.setup_platform(self.hass, {}, mock.MagicMock(), '192.0.2.1')

        # Ensure registration took place (#2558)
        self.assertEqual(len(sonos.DEVICES), 1)
        self.assertEqual(sonos.DEVICES[0].name, 'Kitchen')

    @mock.patch('soco.SoCo', new=SoCoMock)
    def test_ensure_setup_config(self):
        """Test a single address config'd by the HASS config file."""
        sonos.setup_platform(self.hass,
                             {'hosts': '192.0.2.1'},
                             mock.MagicMock())

        # Ensure registration took place (#2558)
        self.assertEqual(len(sonos.DEVICES), 1)
        self.assertEqual(sonos.DEVICES[0].name, 'Kitchen')

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch.object(soco, 'discover', new=socoDiscoverMock.discover)
    def test_ensure_setup_sonos_discovery(self):
        """Test a single device using the autodiscovery provided by Sonos."""
        sonos.setup_platform(self.hass, {}, mock.MagicMock())
        self.assertEqual(len(sonos.DEVICES), 1)
        self.assertEqual(sonos.DEVICES[0].name, 'Kitchen')

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch.object(SoCoMock, 'partymode')
    def test_sonos_group_players(self, partymodeMock):
        """Ensuring soco methods called for sonos_group_players service."""
        sonos.setup_platform(self.hass, {}, mock.MagicMock(), '192.0.2.1')
        device = sonos.DEVICES[-1]
        partymodeMock.return_value = True
        device.group_players()
        partymodeMock.assert_called_once_with()

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch.object(SoCoMock, 'unjoin')
    def test_sonos_unjoin(self, unjoinMock):
        """Ensuring soco methods called for sonos_unjoin service."""
        sonos.setup_platform(self.hass, {}, mock.MagicMock(), '192.0.2.1')
        device = sonos.DEVICES[-1]
        unjoinMock.return_value = True
        device.unjoin()
        unjoinMock.assert_called_once_with()

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch.object(soco.snapshot.Snapshot, 'snapshot')
    def test_sonos_snapshot(self, snapshotMock):
        """Ensuring soco methods called for sonos_snapshot service."""
        sonos.setup_platform(self.hass, {}, mock.MagicMock(), '192.0.2.1')
        device = sonos.DEVICES[-1]
        snapshotMock.return_value = True
        device.snapshot()
        snapshotMock.assert_called_once_with()

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch.object(soco.snapshot.Snapshot, 'restore')
    def test_sonos_restore(self, restoreMock):
        """Ensuring soco methods called for sonos_restor service."""
        sonos.setup_platform(self.hass, {}, mock.MagicMock(), '192.0.2.1')
        device = sonos.DEVICES[-1]
        restoreMock.return_value = True
        device.restore()
        restoreMock.assert_called_once_with(True)
