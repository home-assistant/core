"""The tests for the Demo Media player platform."""
import socket
import unittest
import soco.snapshot
from unittest import mock
import soco

from homeassistant.bootstrap import setup_component
from homeassistant.components.media_player import sonos, DOMAIN
from homeassistant.components.media_player.sonos import CONF_INTERFACE_ADDR, \
    CONF_ADVERTISE_ADDR
from homeassistant.const import CONF_HOSTS, CONF_PLATFORM

from tests.common import get_test_home_assistant

ENTITY_ID = 'media_player.kitchen'


class socoDiscoverMock():
    """Mock class for the soco.discover method."""

    def discover(interface_addr):
        """Return tuple of soco.SoCo objects representing found speakers."""
        return {SoCoMock('192.0.2.1')}


class AvTransportMock():
    """Mock class for the avTransport property on soco.SoCo object."""

    def __init__(self):
        """Initialize ethe Transport mock."""
        pass

    def GetMediaInfo(self, _):
        """Get the media details."""
        return {
            'CurrentURI': '',
            'CurrentURIMetaData': ''
        }


class SoCoMock():
    """Mock class for the soco.SoCo object."""

    def __init__(self, ip):
        """Initialize soco object."""
        self.ip_address = ip
        self.is_visible = True
        self.avTransport = AvTransportMock()

    def clear_sleep_timer(self):
        """Clear the sleep timer."""
        return

    def get_speaker_info(self, force):
        """Return a dict with various data points about the speaker."""
        return {'serial_number': 'B8-E9-37-BO-OC-BA:2',
                'software_version': '32.11-30071',
                'uid': 'RINCON_B8E937BOOCBA02500',
                'zone_icon': 'x-rincon-roomicon:kitchen',
                'mac_address': 'B8:E9:37:BO:OC:BA',
                'zone_name': 'Kitchen',
                'hardware_version': '1.8.1.2-1'}

    def get_current_transport_info(self):
        """Return a dict with the current state of the speaker."""
        return {'current_transport_speed': '1',
                'current_transport_state': 'STOPPED',
                'current_transport_status': 'OK'}

    def get_current_track_info(self):
        """Return a dict with the current track information."""
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
        """Return true if coordinator."""
        return True

    def partymode(self):
        """Cause the speaker to join all other speakers in the network."""
        return

    def set_sleep_timer(self, sleep_time_seconds):
        """Set the sleep timer."""
        return

    def unjoin(self):
        """Cause the speaker to separate itself from other speakers."""
        return

    def uid(self):
        """Return a player uid."""
        return "RINCON_XXXXXXXXXXXXXXXXX"


def fake_add_device(devices, update_befor_add=False):
    """Fake add device / update."""
    if update_befor_add:
        for speaker in devices:
            speaker.update()


class TestSonosMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        def monkey_available(self):
            """Make a monkey available."""
            return True

        # Monkey patches
        self.real_available = sonos.SonosDevice.available
        sonos.SonosDevice.available = monkey_available

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        # Monkey patches
        sonos.SonosDevice.available = self.real_available
        sonos.DEVICES = []
        self.hass.stop()

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    def test_ensure_setup_discovery(self, *args):
        """Test a single device using the autodiscovery provided by HASS."""
        sonos.setup_platform(self.hass, {}, fake_add_device, '192.0.2.1')

        self.assertEqual(len(sonos.DEVICES), 1)
        self.assertEqual(sonos.DEVICES[0].name, 'Kitchen')

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch('soco.discover')
    def test_ensure_setup_config_interface_addr(self, discover_mock, *args):
        """Test a interface address config'd by the HASS config file."""
        discover_mock.return_value = {SoCoMock('192.0.2.1')}

        config = {
            DOMAIN: {
                CONF_PLATFORM: 'sonos',
                CONF_INTERFACE_ADDR: '192.0.1.1',
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        self.assertEqual(len(sonos.DEVICES), 1)
        self.assertEqual(discover_mock.call_count, 1)

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch('soco.discover')
    def test_ensure_setup_config_advertise_addr(self, discover_mock,
                                                *args):
        """Test a advertise address config'd by the HASS config file."""
        discover_mock.return_value = {SoCoMock('192.0.2.1')}

        config = {
            DOMAIN: {
                CONF_PLATFORM: 'sonos',
                CONF_ADVERTISE_ADDR: '192.0.1.1',
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        self.assertEqual(len(sonos.DEVICES), 1)
        self.assertEqual(discover_mock.call_count, 1)
        self.assertEqual(soco.config.EVENT_ADVERTISE_IP, '192.0.1.1')

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    def test_ensure_setup_config_hosts_string_single(self, *args):
        """Test a single address config'd by the HASS config file."""
        config = {
            DOMAIN: {
                CONF_PLATFORM: 'sonos',
                CONF_HOSTS: ['192.0.2.1'],
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        self.assertEqual(len(sonos.DEVICES), 1)
        self.assertEqual(sonos.DEVICES[0].name, 'Kitchen')

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    def test_ensure_setup_config_hosts_string_multiple(self, *args):
        """Test multiple address string config'd by the HASS config file."""
        config = {
            DOMAIN: {
                CONF_PLATFORM: 'sonos',
                CONF_HOSTS: ['192.0.2.1,192.168.2.2'],
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        self.assertEqual(len(sonos.DEVICES), 2)
        self.assertEqual(sonos.DEVICES[0].name, 'Kitchen')

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    def test_ensure_setup_config_hosts_list(self, *args):
        """Test a multiple address list config'd by the HASS config file."""
        config = {
            DOMAIN: {
                CONF_PLATFORM: 'sonos',
                CONF_HOSTS: ['192.0.2.1', '192.168.2.2'],
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        self.assertEqual(len(sonos.DEVICES), 2)
        self.assertEqual(sonos.DEVICES[0].name, 'Kitchen')

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch.object(soco, 'discover', new=socoDiscoverMock.discover)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    def test_ensure_setup_sonos_discovery(self, *args):
        """Test a single device using the autodiscovery provided by Sonos."""
        sonos.setup_platform(self.hass, {}, fake_add_device)
        self.assertEqual(len(sonos.DEVICES), 1)
        self.assertEqual(sonos.DEVICES[0].name, 'Kitchen')

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(SoCoMock, 'partymode')
    def test_sonos_group_players(self, partymodeMock, *args):
        """Ensuring soco methods called for sonos_group_players service."""
        sonos.setup_platform(self.hass, {}, fake_add_device, '192.0.2.1')
        device = sonos.DEVICES[-1]
        partymodeMock.return_value = True
        device.group_players()
        self.assertEqual(partymodeMock.call_count, 1)
        self.assertEqual(partymodeMock.call_args, mock.call())

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(SoCoMock, 'unjoin')
    def test_sonos_unjoin(self, unjoinMock, *args):
        """Ensuring soco methods called for sonos_unjoin service."""
        sonos.setup_platform(self.hass, {}, fake_add_device, '192.0.2.1')
        device = sonos.DEVICES[-1]
        unjoinMock.return_value = True
        device.unjoin()
        self.assertEqual(unjoinMock.call_count, 1)
        self.assertEqual(unjoinMock.call_args, mock.call())

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(SoCoMock, 'set_sleep_timer')
    def test_sonos_set_sleep_timer(self, set_sleep_timerMock, *args):
        """Ensuring soco methods called for sonos_set_sleep_timer service."""
        sonos.setup_platform(self.hass, {}, fake_add_device, '192.0.2.1')
        device = sonos.DEVICES[-1]
        device.set_sleep_timer(30)
        set_sleep_timerMock.assert_called_once_with(30)

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(SoCoMock, 'set_sleep_timer')
    def test_sonos_clear_sleep_timer(self, set_sleep_timerMock, *args):
        """Ensuring soco methods called for sonos_clear_sleep_timer service."""
        sonos.setup_platform(self.hass, {}, mock.MagicMock(), '192.0.2.1')
        device = sonos.DEVICES[-1]
        device.set_sleep_timer(None)
        set_sleep_timerMock.assert_called_once_with(None)

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(soco.snapshot.Snapshot, 'snapshot')
    def test_sonos_snapshot(self, snapshotMock, *args):
        """Ensuring soco methods called for sonos_snapshot service."""
        sonos.setup_platform(self.hass, {}, fake_add_device, '192.0.2.1')
        device = sonos.DEVICES[-1]
        snapshotMock.return_value = True
        device.snapshot()
        self.assertEqual(snapshotMock.call_count, 1)
        self.assertEqual(snapshotMock.call_args, mock.call())

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(soco.snapshot.Snapshot, 'restore')
    def test_sonos_restore(self, restoreMock, *args):
        """Ensuring soco methods called for sonos_restor service."""
        sonos.setup_platform(self.hass, {}, fake_add_device, '192.0.2.1')
        device = sonos.DEVICES[-1]
        restoreMock.return_value = True
        device.restore()
        self.assertEqual(restoreMock.call_count, 1)
        self.assertEqual(restoreMock.call_args, mock.call(True))
