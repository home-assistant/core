"""The tests for the Demo Media player platform."""
import datetime
import socket
import unittest
import pysonos.snapshot
from unittest import mock
import pysonos
from pysonos import alarms

from homeassistant.setup import setup_component
from homeassistant.components.sonos import media_player as sonos
from homeassistant.components.media_player.const import DOMAIN
from homeassistant.components.sonos.media_player import CONF_INTERFACE_ADDR
from homeassistant.const import CONF_HOSTS, CONF_PLATFORM
from homeassistant.util.async_ import run_coroutine_threadsafe

from tests.common import get_test_home_assistant

ENTITY_ID = 'media_player.kitchen'


class pysonosDiscoverMock():
    """Mock class for the pysonos.discover method."""

    def discover(interface_addr, all_households=False):
        """Return tuple of pysonos.SoCo objects representing found speakers."""
        return {SoCoMock('192.0.2.1')}


class AvTransportMock():
    """Mock class for the avTransport property on pysonos.SoCo object."""

    def __init__(self):
        """Initialize ethe Transport mock."""
        pass

    def GetMediaInfo(self, _):
        """Get the media details."""
        return {
            'CurrentURI': '',
            'CurrentURIMetaData': ''
        }


class MusicLibraryMock():
    """Mock class for the music_library property on pysonos.SoCo object."""

    def get_sonos_favorites(self):
        """Return favorites."""
        return []


class CacheMock():
    """Mock class for the _zgs_cache property on pysonos.SoCo object."""

    def clear(self):
        """Clear cache."""
        pass


class SoCoMock():
    """Mock class for the pysonos.SoCo object."""

    def __init__(self, ip):
        """Initialize SoCo object."""
        self.ip_address = ip
        self.is_visible = True
        self.volume = 50
        self.mute = False
        self.shuffle = False
        self.night_mode = False
        self.dialog_mode = False
        self.music_library = MusicLibraryMock()
        self.avTransport = AvTransportMock()
        self._zgs_cache = CacheMock()

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
                'model_name': 'Sonos PLAY:1',
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


def add_entities_factory(hass):
    """Add entities factory."""
    def add_entities(entities, update_befor_add=False):
        """Fake add entity."""
        hass.data[sonos.DATA_SONOS].entities = list(entities)

    return add_entities


class TestSonosMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        def monkey_available(self):
            """Make a monkey available."""
            return True

        # Monkey patches
        self.real_available = sonos.SonosEntity.available
        sonos.SonosEntity.available = monkey_available

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        # Monkey patches
        sonos.SonosEntity.available = self.real_available
        self.hass.stop()

    @mock.patch('pysonos.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    def test_ensure_setup_discovery(self, *args):
        """Test a single device using the autodiscovery provided by HASS."""
        sonos.setup_platform(self.hass, {}, add_entities_factory(self.hass), {
            'host': '192.0.2.1'
        })

        entities = self.hass.data[sonos.DATA_SONOS].entities
        assert len(entities) == 1
        assert entities[0].name == 'Kitchen'

    @mock.patch('pysonos.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch('pysonos.discover')
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

        assert len(self.hass.data[sonos.DATA_SONOS].entities) == 1
        assert discover_mock.call_count == 1

    @mock.patch('pysonos.SoCo', new=SoCoMock)
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

        entities = self.hass.data[sonos.DATA_SONOS].entities
        assert len(entities) == 1
        assert entities[0].name == 'Kitchen'

    @mock.patch('pysonos.SoCo', new=SoCoMock)
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

        entities = self.hass.data[sonos.DATA_SONOS].entities
        assert len(entities) == 2
        assert entities[0].name == 'Kitchen'

    @mock.patch('pysonos.SoCo', new=SoCoMock)
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

        entities = self.hass.data[sonos.DATA_SONOS].entities
        assert len(entities) == 2
        assert entities[0].name == 'Kitchen'

    @mock.patch('pysonos.SoCo', new=SoCoMock)
    @mock.patch.object(pysonos, 'discover', new=pysonosDiscoverMock.discover)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    def test_ensure_setup_sonos_discovery(self, *args):
        """Test a single device using the autodiscovery provided by Sonos."""
        sonos.setup_platform(self.hass, {}, add_entities_factory(self.hass))
        entities = self.hass.data[sonos.DATA_SONOS].entities
        assert len(entities) == 1
        assert entities[0].name == 'Kitchen'

    @mock.patch('pysonos.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(SoCoMock, 'set_sleep_timer')
    def test_sonos_set_sleep_timer(self, set_sleep_timerMock, *args):
        """Ensure pysonos methods called for sonos_set_sleep_timer service."""
        sonos.setup_platform(self.hass, {}, add_entities_factory(self.hass), {
            'host': '192.0.2.1'
        })
        entity = self.hass.data[sonos.DATA_SONOS].entities[-1]
        entity.hass = self.hass

        entity.set_sleep_timer(30)
        set_sleep_timerMock.assert_called_once_with(30)

    @mock.patch('pysonos.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(SoCoMock, 'set_sleep_timer')
    def test_sonos_clear_sleep_timer(self, set_sleep_timerMock, *args):
        """Ensure pysonos method called for sonos_clear_sleep_timer service."""
        sonos.setup_platform(self.hass, {}, add_entities_factory(self.hass), {
            'host': '192.0.2.1'
        })
        entity = self.hass.data[sonos.DATA_SONOS].entities[-1]
        entity.hass = self.hass

        entity.set_sleep_timer(None)
        set_sleep_timerMock.assert_called_once_with(None)

    @mock.patch('pysonos.SoCo', new=SoCoMock)
    @mock.patch('pysonos.alarms.Alarm')
    @mock.patch('socket.create_connection', side_effect=socket.error())
    def test_set_alarm(self, pysonos_mock, alarm_mock, *args):
        """Ensure pysonos methods called for sonos_set_sleep_timer service."""
        sonos.setup_platform(self.hass, {}, add_entities_factory(self.hass), {
            'host': '192.0.2.1'
        })
        entity = self.hass.data[sonos.DATA_SONOS].entities[-1]
        entity.hass = self.hass
        alarm1 = alarms.Alarm(pysonos_mock)
        alarm1.configure_mock(_alarm_id="1", start_time=None, enabled=False,
                              include_linked_zones=False, volume=100)
        with mock.patch('pysonos.alarms.get_alarms', return_value=[alarm1]):
            attrs = {
                'time': datetime.time(12, 00),
                'enabled': True,
                'include_linked_zones': True,
                'volume': 0.30,
            }
            entity.set_alarm(alarm_id=2)
            alarm1.save.assert_not_called()
            entity.set_alarm(alarm_id=1, **attrs)
            assert alarm1.enabled == attrs['enabled']
            assert alarm1.start_time == attrs['time']
            assert alarm1.include_linked_zones == \
                attrs['include_linked_zones']
            assert alarm1.volume == 30
            alarm1.save.assert_called_once_with()

    @mock.patch('pysonos.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(pysonos.snapshot.Snapshot, 'snapshot')
    def test_sonos_snapshot(self, snapshotMock, *args):
        """Ensure pysonos methods called for sonos_snapshot service."""
        sonos.setup_platform(self.hass, {}, add_entities_factory(self.hass), {
            'host': '192.0.2.1'
        })
        entities = self.hass.data[sonos.DATA_SONOS].entities
        entity = entities[-1]
        entity.hass = self.hass

        snapshotMock.return_value = True
        entity.soco.group = mock.MagicMock()
        entity.soco.group.members = [e.soco for e in entities]
        run_coroutine_threadsafe(
            sonos.SonosEntity.snapshot_multi(self.hass, entities, True),
            self.hass.loop).result()
        assert snapshotMock.call_count == 1
        assert snapshotMock.call_args == mock.call()

    @mock.patch('pysonos.SoCo', new=SoCoMock)
    @mock.patch('socket.create_connection', side_effect=socket.error())
    @mock.patch.object(pysonos.snapshot.Snapshot, 'restore')
    def test_sonos_restore(self, restoreMock, *args):
        """Ensure pysonos methods called for sonos_restore service."""
        from pysonos.snapshot import Snapshot

        sonos.setup_platform(self.hass, {}, add_entities_factory(self.hass), {
            'host': '192.0.2.1'
        })
        entities = self.hass.data[sonos.DATA_SONOS].entities
        entity = entities[-1]
        entity.hass = self.hass

        restoreMock.return_value = True
        entity._snapshot_group = mock.MagicMock()
        entity._snapshot_group.members = [e.soco for e in entities]
        entity._soco_snapshot = Snapshot(entity.soco)
        run_coroutine_threadsafe(
            sonos.SonosEntity.restore_multi(self.hass, entities, True),
            self.hass.loop).result()
        assert restoreMock.call_count == 1
        assert restoreMock.call_args == mock.call()
