"""The tests for the Demo Media player platform."""
import datetime
import socket
import unittest
import soco.snapshot
from unittest import mock
import soco
from soco import alarms

from homeassistant.setup import setup_component
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

    def get_sonos_favorites(self):
        """Get favorites list from sonos."""
        return {'favorites': []}

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

    def join(self, master):
        """Join speaker to a group."""
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

    def group(self):
        """Return all group data of this player."""
        return


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
        self.hass.stop()

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    def test_ensure_setup_discovery(self, *args):
        """Test a single device using the autodiscovery provided by HASS."""
        sonos.setup_platform(self.hass, {}, fake_add_device, {
            'host': '192.0.2.1'
        })

        self.assertEqual(len(self.hass.data[sonos.DATA_SONOS]), 1)
        self.assertEqual(self.hass.data[sonos.DATA_SONOS][0].name, 'Kitchen')

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch('soco.discover')
    def test_ensure_setup_config_interface_addr(self, discover_mock, *args):
        """Test an interface address config'd by the HASS config file."""
        discover_mock.return_value = {SoCoMock('192.0.2.1')}

        config = {
            DOMAIN: {
                CONF_PLATFORM: 'sonos',
                CONF_INTERFACE_ADDR: '192.0.1.1',
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        self.assertEqual(len(self.hass.data[sonos.DATA_SONOS]), 1)
        self.assertEqual(discover_mock.call_count, 1)

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch('soco.discover')
    def test_ensure_setup_config_advertise_addr(self, discover_mock,
                                                *args):
        """Test an advertise address config'd by the HASS config file."""
        discover_mock.return_value = {SoCoMock('192.0.2.1')}

        config = {
            DOMAIN: {
                CONF_PLATFORM: 'sonos',
                CONF_ADVERTISE_ADDR: '192.0.1.1',
            }
        }

        assert setup_component(self.hass, DOMAIN, config)

        self.assertEqual(len(self.hass.data[sonos.DATA_SONOS]), 1)
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

        self.assertEqual(len(self.hass.data[sonos.DATA_SONOS]), 1)
        self.assertEqual(self.hass.data[sonos.DATA_SONOS][0].name, 'Kitchen')

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

        self.assertEqual(len(self.hass.data[sonos.DATA_SONOS]), 2)
        self.assertEqual(self.hass.data[sonos.DATA_SONOS][0].name, 'Kitchen')

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

        self.assertEqual(len(self.hass.data[sonos.DATA_SONOS]), 2)
        self.assertEqual(self.hass.data[sonos.DATA_SONOS][0].name, 'Kitchen')

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch.object(soco, 'discover', new=socoDiscoverMock.discover)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    def test_ensure_setup_sonos_discovery(self, *args):
        """Test a single device using the autodiscovery provided by Sonos."""
        sonos.setup_platform(self.hass, {}, fake_add_device)
        self.assertEqual(len(self.hass.data[sonos.DATA_SONOS]), 1)
        self.assertEqual(self.hass.data[sonos.DATA_SONOS][0].name, 'Kitchen')

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(SoCoMock, 'join')
    def test_sonos_group_players(self, join_mock, *args):
        """Ensuring soco methods called for sonos_group_players service."""
        sonos.setup_platform(self.hass, {}, fake_add_device, {
            'host': '192.0.2.1'
        })
        device = self.hass.data[sonos.DATA_SONOS][-1]
        device.hass = self.hass

        device_master = mock.MagicMock()
        device_master.entity_id = "media_player.test"
        device_master.soco_device = mock.MagicMock()
        self.hass.data[sonos.DATA_SONOS].append(device_master)

        join_mock.return_value = True
        device.join("media_player.test")
        self.assertEqual(join_mock.call_count, 1)

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(SoCoMock, 'unjoin')
    def test_sonos_unjoin(self, unjoinMock, *args):
        """Ensuring soco methods called for sonos_unjoin service."""
        sonos.setup_platform(self.hass, {}, fake_add_device, {
            'host': '192.0.2.1'
        })
        device = self.hass.data[sonos.DATA_SONOS][-1]
        device.hass = self.hass

        unjoinMock.return_value = True
        device.unjoin()
        self.assertEqual(unjoinMock.call_count, 1)
        self.assertEqual(unjoinMock.call_args, mock.call())

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    def test_set_shuffle(self, shuffle_set_mock, *args):
        """Ensuring soco methods called for sonos_snapshot service."""
        sonos.setup_platform(self.hass, {}, fake_add_device, {
            'host': '192.0.2.1'
        })
        device = self.hass.data[sonos.DATA_SONOS][-1]
        device.hass = self.hass

        device.set_shuffle(True)
        self.assertEqual(shuffle_set_mock.call_count, 1)
        self.assertEqual(device._player.play_mode, 'SHUFFLE')

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(SoCoMock, 'set_sleep_timer')
    def test_sonos_set_sleep_timer(self, set_sleep_timerMock, *args):
        """Ensuring soco methods called for sonos_set_sleep_timer service."""
        sonos.setup_platform(self.hass, {}, fake_add_device, {
            'host': '192.0.2.1'
        })
        device = self.hass.data[sonos.DATA_SONOS][-1]
        device.hass = self.hass

        device.set_sleep_timer(30)
        set_sleep_timerMock.assert_called_once_with(30)

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(SoCoMock, 'set_sleep_timer')
    def test_sonos_clear_sleep_timer(self, set_sleep_timerMock, *args):
        """Ensuring soco methods called for sonos_clear_sleep_timer service."""
        sonos.setup_platform(self.hass, {}, mock.MagicMock(), {
            'host': '192.0.2.1'
        })
        device = self.hass.data[sonos.DATA_SONOS][-1]
        device.hass = self.hass

        device.set_sleep_timer(None)
        set_sleep_timerMock.assert_called_once_with(None)

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('soco.alarms.Alarm')
    @mock.patch('socket.create_connection', side_effect=socket.error())
    def test_update_alarm(self, soco_mock, alarm_mock, *args):
        """Ensuring soco methods called for sonos_set_sleep_timer service."""
        sonos.setup_platform(self.hass, {}, fake_add_device, {
            'host': '192.0.2.1'
        })
        device = self.hass.data[sonos.DATA_SONOS][-1]
        device.hass = self.hass
        alarm1 = alarms.Alarm(soco_mock)
        alarm1.configure_mock(_alarm_id="1", start_time=None, enabled=False,
                              include_linked_zones=False, volume=100)
        with mock.patch('soco.alarms.get_alarms', return_value=[alarm1]):
            attrs = {
                'time': datetime.time(12, 00),
                'enabled': True,
                'include_linked_zones': True,
                'volume': 0.30,
            }
            device.update_alarm(alarm_id=2)
            alarm1.save.assert_not_called()
            device.update_alarm(alarm_id=1, **attrs)
            self.assertEqual(alarm1.enabled, attrs['enabled'])
            self.assertEqual(alarm1.start_time, attrs['time'])
            self.assertEqual(alarm1.include_linked_zones,
                             attrs['include_linked_zones'])
            self.assertEqual(alarm1.volume, 30)
            alarm1.save.assert_called_once_with()

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(soco.snapshot.Snapshot, 'snapshot')
    def test_sonos_snapshot(self, snapshotMock, *args):
        """Ensuring soco methods called for sonos_snapshot service."""
        sonos.setup_platform(self.hass, {}, fake_add_device, {
            'host': '192.0.2.1'
        })
        device = self.hass.data[sonos.DATA_SONOS][-1]
        device.hass = self.hass

        snapshotMock.return_value = True
        device.snapshot()
        self.assertEqual(snapshotMock.call_count, 1)
        self.assertEqual(snapshotMock.call_args, mock.call())

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(soco.snapshot.Snapshot, 'restore')
    def test_sonos_restore(self, restoreMock, *args):
        """Ensuring soco methods called for sonos_restor service."""
        from soco.snapshot import Snapshot

        sonos.setup_platform(self.hass, {}, fake_add_device, {
            'host': '192.0.2.1'
        })
        device = self.hass.data[sonos.DATA_SONOS][-1]
        device.hass = self.hass

        restoreMock.return_value = True
        device._snapshot_coordinator = mock.MagicMock()
        device._snapshot_coordinator.soco_device = SoCoMock('192.0.2.17')
        device._soco_snapshot = Snapshot(device._player)
        device.restore()
        self.assertEqual(restoreMock.call_count, 1)
        self.assertEqual(restoreMock.call_args, mock.call(False))

    @mock.patch('soco.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    def test_sonos_set_option(self, option_mock, *args):
        """Ensuring soco methods called for sonos_set_option service."""
        sonos.setup_platform(self.hass, {}, fake_add_device, {
            'host': '192.0.2.1'
        })
        device = self.hass.data[sonos.DATA_SONOS][-1]
        device.hass = self.hass

        option_mock.return_value = True
        device._snapshot_coordinator = mock.MagicMock()
        device._snapshot_coordinator.soco_device = SoCoMock('192.0.2.17')

        device.update_option(night_sound=True, speech_enhance=True)

        self.assertEqual(option_mock.call_count, 1)
