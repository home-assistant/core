"""
Support for Bluesound devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.bluesound/
"""
import asyncio
from asyncio.futures import CancelledError
from datetime import timedelta
import logging

import aiohttp
from aiohttp.client_exceptions import ClientError
from aiohttp.hdrs import CONNECTION, KEEP_ALIVE
import async_timeout
import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_MUSIC, PLATFORM_SCHEMA, SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK, SUPPORT_SELECT_SOURCE, SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP,
    MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_HOSTS, CONF_NAME, CONF_PORT, EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP, STATE_IDLE, STATE_PAUSED, STATE_PLAYING)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['xmltodict==0.11.0']

_LOGGER = logging.getLogger(__name__)

STATE_OFFLINE = 'offline'
ATTR_MODEL = 'model'
ATTR_MODEL_NAME = 'model_name'
ATTR_BRAND = 'brand'

DATA_BLUESOUND = 'bluesound'
DEFAULT_PORT = 11000

SYNC_STATUS_INTERVAL = timedelta(minutes=5)
UPDATE_CAPTURE_INTERVAL = timedelta(minutes=30)
UPDATE_SERVICES_INTERVAL = timedelta(minutes=30)
UPDATE_PRESETS_INTERVAL = timedelta(minutes=30)
NODE_OFFLINE_CHECK_TIMEOUT = 180
NODE_RETRY_INITIATION = timedelta(minutes=3)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOSTS): vol.All(cv.ensure_list, [{
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME): cv.string,
    }])
})


def _add_player(hass, async_add_devices, host, port=None, name=None):
    """Add Bluesound players."""
    if host in [x.host for x in hass.data[DATA_BLUESOUND]]:
        return

    @callback
    def _init_player(event=None):
        """Start polling."""
        hass.async_add_job(player.async_init())

    @callback
    def _start_polling(event=None):
        """Start polling."""
        player.start_polling()

    @callback
    def _stop_polling():
        """Stop polling."""
        player.stop_polling()

    @callback
    def _add_player_cb():
        """Add player after first sync fetch."""
        async_add_devices([player])
        _LOGGER.info("Added device with name: %s", player.name)

        if hass.is_running:
            _start_polling()
        else:
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, _start_polling)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_polling)

    player = BluesoundPlayer(hass, host, port, name, _add_player_cb)
    hass.data[DATA_BLUESOUND].append(player)

    if hass.is_running:
        _init_player()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _init_player)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Bluesound platforms."""
    if DATA_BLUESOUND not in hass.data:
        hass.data[DATA_BLUESOUND] = []

    if discovery_info:
        _add_player(hass, async_add_devices, discovery_info.get(CONF_HOST),
                    discovery_info.get(CONF_PORT, None))
        return

    hosts = config.get(CONF_HOSTS, None)
    if hosts:
        for host in hosts:
            _add_player(
                hass, async_add_devices, host.get(CONF_HOST),
                host.get(CONF_PORT), host.get(CONF_NAME))


class BluesoundPlayer(MediaPlayerDevice):
    """Representation of a Bluesound Player."""

    def __init__(self, hass, host, port=None, name=None, init_callback=None):
        """Initialize the media player."""
        self.host = host
        self._hass = hass
        self._port = port
        self._polling_session = async_get_clientsession(hass)
        self._polling_task = None  # The actual polling task.
        self._name = name
        self._brand = None
        self._model = None
        self._model_name = None
        self._icon = None
        self._capture_items = []
        self._services_items = []
        self._preset_items = []
        self._sync_status = {}
        self._status = None
        self._last_status_update = None
        self._is_online = False
        self._retry_remove = None
        self._lastvol = None
        self._init_callback = init_callback
        if self._port is None:
            self._port = DEFAULT_PORT

    @staticmethod
    def _try_get_index(string, search_string):
        """Get the index."""
        try:
            return string.index(search_string)
        except ValueError:
            return -1

    @asyncio.coroutine
    def _internal_update_sync_status(
            self, on_updated_cb=None, raise_timeout=False):
        """Update the internal status."""
        resp = None
        try:
            resp = yield from self.send_bluesound_command(
                'SyncStatus', raise_timeout, raise_timeout)
        except Exception:
            raise

        if not resp:
            return None
        self._sync_status = resp['SyncStatus'].copy()

        if not self._name:
            self._name = self._sync_status.get('@name', self.host)
        if not self._brand:
            self._brand = self._sync_status.get('@brand', self.host)
        if not self._model:
            self._model = self._sync_status.get('@model', self.host)
        if not self._icon:
            self._icon = self._sync_status.get('@icon', self.host)
        if not self._model_name:
            self._model_name = self._sync_status.get('@modelName', self.host)

        if on_updated_cb:
            on_updated_cb()
        return True

    @asyncio.coroutine
    def _start_poll_command(self):
        """Loop which polls the status of the player."""
        try:
            while True:
                yield from self.async_update_status()

        except (asyncio.TimeoutError, ClientError):
            _LOGGER.info("Node %s is offline, retrying later", self._name)
            yield from asyncio.sleep(
                NODE_OFFLINE_CHECK_TIMEOUT, loop=self._hass.loop)
            self.start_polling()

        except CancelledError:
            _LOGGER.debug("Stopping the polling of node %s", self._name)
        except Exception:
            _LOGGER.exception("Unexpected error in %s", self._name)
            raise

    def start_polling(self):
        """Start the polling task."""
        self._polling_task = self._hass.async_add_job(
            self._start_poll_command())

    def stop_polling(self):
        """Stop the polling task."""
        self._polling_task.cancel()

    @asyncio.coroutine
    def async_init(self):
        """Initialize the player async."""
        try:
            if self._retry_remove is not None:
                self._retry_remove()
                self._retry_remove = None

            yield from self._internal_update_sync_status(
                self._init_callback, True)
        except (asyncio.TimeoutError, ClientError):
            _LOGGER.info("Node %s is offline, retrying later", self.host)
            self._retry_remove = async_track_time_interval(
                self._hass, self.async_init, NODE_RETRY_INITIATION)
        except Exception:
            _LOGGER.exception("Unexpected when initiating error in %s",
                              self.host)
            raise

    @asyncio.coroutine
    def async_update(self):
        """Update internal status of the entity."""
        if not self._is_online:
            return

        yield from self.async_update_sync_status()
        yield from self.async_update_presets()
        yield from self.async_update_captures()
        yield from self.async_update_services()

    @asyncio.coroutine
    def send_bluesound_command(self, method, raise_timeout=False,
                               allow_offline=False):
        """Send command to the player."""
        import xmltodict

        if not self._is_online and not allow_offline:
            return

        if method[0] == '/':
            method = method[1:]
        url = "http://{}:{}/{}".format(self.host, self._port, method)

        _LOGGER.debug("Calling URL: %s", url)
        response = None
        try:
            websession = async_get_clientsession(self._hass)
            with async_timeout.timeout(10, loop=self._hass.loop):
                response = yield from websession.get(url)

            if response.status == 200:
                result = yield from response.text()
                if len(result) < 1:
                    data = None
                else:
                    data = xmltodict.parse(result)
            else:
                _LOGGER.error("Error %s on %s", response.status, url)
                return None

        except (asyncio.TimeoutError, aiohttp.ClientError):
            if raise_timeout:
                _LOGGER.info("Timeout: %s", self.host)
                raise
            else:
                _LOGGER.debug("Failed communicating: %s", self.host)
                return None

        return data

    @asyncio.coroutine
    def async_update_status(self):
        """Use the poll session to always get the status of the player."""
        import xmltodict
        response = None

        url = 'Status'
        etag = ''
        if self._status is not None:
            etag = self._status.get('@etag', '')

        if etag != '':
            url = 'Status?etag={}&timeout=60.0'.format(etag)
        url = "http://{}:{}/{}".format(self.host, self._port, url)

        _LOGGER.debug("Calling URL: %s", url)

        try:

            with async_timeout.timeout(65, loop=self._hass.loop):
                response = yield from self._polling_session.get(
                    url,
                    headers={CONNECTION: KEEP_ALIVE})

            if response.status != 200:
                _LOGGER.error("Error %s on %s", response.status, url)

            result = yield from response.text()
            self._is_online = True
            self._last_status_update = dt_util.utcnow()
            self._status = xmltodict.parse(result)['status'].copy()
            self.schedule_update_ha_state()

        except (asyncio.TimeoutError, ClientError):
            self._is_online = False
            self._last_status_update = None
            self._status = None
            self.schedule_update_ha_state()
            _LOGGER.info("Client connection error, marking %s as offline",
                         self._name)
            raise

    @asyncio.coroutine
    @Throttle(SYNC_STATUS_INTERVAL)
    def async_update_sync_status(self, on_updated_cb=None,
                                 raise_timeout=False):
        """Update sync status."""
        yield from self._internal_update_sync_status(
            on_updated_cb, raise_timeout=False)

    @asyncio.coroutine
    @Throttle(UPDATE_CAPTURE_INTERVAL)
    def async_update_captures(self):
        """Update Capture sources."""
        resp = yield from self.send_bluesound_command(
            'RadioBrowse?service=Capture')
        if not resp:
            return
        self._capture_items = []

        def _create_capture_item(item):
            self._capture_items.append({
                'title': item.get('@text', ''),
                'name': item.get('@text', ''),
                'type': item.get('@serviceType', 'Capture'),
                'image': item.get('@image', ''),
                'url': item.get('@URL', '')
            })

        if 'radiotime' in resp and 'item' in resp['radiotime']:
            if isinstance(resp['radiotime']['item'], list):
                for item in resp['radiotime']['item']:
                    _create_capture_item(item)
            else:
                _create_capture_item(resp['radiotime']['item'])

        return self._capture_items

    @asyncio.coroutine
    @Throttle(UPDATE_PRESETS_INTERVAL)
    def async_update_presets(self):
        """Update Presets."""
        resp = yield from self.send_bluesound_command('Presets')
        if not resp:
            return
        self._preset_items = []

        def _create_preset_item(item):
            self._preset_items.append({
                'title': item.get('@name', ''),
                'name': item.get('@name', ''),
                'type': 'preset',
                'image': item.get('@image', ''),
                'is_raw_url': True,
                'url2': item.get('@url', ''),
                'url': 'Preset?id=' + item.get('@id', '')
            })

        if 'presets' in resp and 'preset' in resp['presets']:
            if isinstance(resp['presets']['preset'], list):
                for item in resp['presets']['preset']:
                    _create_preset_item(item)
            else:
                _create_preset_item(resp['presets']['preset'])

        return self._preset_items

    @asyncio.coroutine
    @Throttle(UPDATE_SERVICES_INTERVAL)
    def async_update_services(self):
        """Update Services."""
        resp = yield from self.send_bluesound_command('Services')
        if not resp:
            return
        self._services_items = []

        def _create_service_item(item):
            self._services_items.append({
                'title': item.get('@displayname', ''),
                'name': item.get('@name', ''),
                'type': item.get('@type', ''),
                'image': item.get('@icon', ''),
                'url': item.get('@name', '')
            })

        if 'services' in resp and 'service' in resp['services']:
            if isinstance(resp['services']['service'], list):
                for item in resp['services']['service']:
                    _create_service_item(item)
            else:
                _create_service_item(resp['services']['service'])

        return self._services_items

    @property
    def should_poll(self):
        """No need to poll information."""
        return True

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def state(self):
        """Return the state of the device."""
        if self._status is None:
            return STATE_OFFLINE

        status = self._status.get('state', None)
        if status == 'pause' or status == 'stop':
            return STATE_PAUSED
        elif status == 'stream' or status == 'play':
            return STATE_PLAYING
        else:
            return STATE_IDLE

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._status is None:
            return None

        return self._status.get('title1', None)

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        if self._status is None:
            return None

        artist = self._status.get('artist', None)
        if not artist:
            artist = self._status.get('title2', None)
        return artist

    @property
    def media_album_name(self):
        """Artist of current playing media (Music track only)."""
        if self._status is None:
            return None

        album = self._status.get('album', None)
        if not album:
            album = self._status.get('title3', None)
        return album

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self._status is None:
            return None

        url = self._status.get('image', None)
        if not url:
            return
        if url[0] == '/':
            url = "http://{}:{}{}".format(self.host, self._port, url)

        return url

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self._status is None:
            return None

        mediastate = self.state
        if self._last_status_update is None or mediastate == STATE_IDLE:
            return None

        position = self._status.get('secs', None)
        if position is None:
            return None

        position = float(position)
        if mediastate == STATE_PLAYING:
            position += (dt_util.utcnow() -
                         self._last_status_update).total_seconds()

        return position

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if self._status is None:
            return None

        duration = self._status.get('totlen', None)
        if duration is None:
            return None
        return float(duration)

    @property
    def media_position_updated_at(self):
        """Last time status was updated."""
        return self._last_status_update

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._status is None:
            return None

        volume = self._status.get('volume', None)
        if volume is not None:
            return int(volume) / 100
        return None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        if not self._status:
            return None

        volume = self.volume_level
        if not volume:
            return None
        return volume < 0.001 and volume >= 0

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the device."""
        return self._icon

    @property
    def source_list(self):
        """List of available input sources."""
        if self._status is None:
            return None

        sources = []

        for source in self._preset_items:
            sources.append(source['title'])

        for source in [x for x in self._services_items
                       if x['type'] == 'LocalMusic' or
                       x['type'] == 'RadioService']:
            sources.append(source['title'])

        for source in self._capture_items:
            sources.append(source['title'])

        return sources

    @property
    def source(self):
        """Name of the current input source."""
        from urllib import parse

        if self._status is None:
            return None

        current_service = self._status.get('service', '')
        if current_service == '':
            return ''
        stream_url = self._status.get('streamUrl', '')

        if self._status.get('is_preset', '') == '1' and stream_url != '':
            # This check doesn't work with all presets, for example playlists.
            # But it works with radio service_items will catch playlists.
            items = [x for x in self._preset_items if 'url2' in x and
                     parse.unquote(x['url2']) == stream_url]
            if len(items) > 0:
                return items[0]['title']

        # This could be a bit difficult to detect. Bluetooth could be named
        # different things and there is not any way to match chooses in
        # capture list to current playing. It's a bit of guesswork.
        # This method will be needing some tweaking over time.
        title = self._status.get('title1', '').lower()
        if title == 'bluetooth' or stream_url == 'Capture:hw:2,0/44100/16/2':
            items = [x for x in self._capture_items
                     if x['url'] == "Capture%3Abluez%3Abluetooth"]
            if len(items) > 0:
                return items[0]['title']

        items = [x for x in self._capture_items if x['url'] == stream_url]
        if len(items) > 0:
            return items[0]['title']

        if stream_url[:8] == 'Capture:':
            stream_url = stream_url[8:]

        idx = BluesoundPlayer._try_get_index(stream_url, ':')
        if idx > 0:
            stream_url = stream_url[:idx]
            for item in self._capture_items:
                url = parse.unquote(item['url'])
                if url[:8] == 'Capture:':
                    url = url[8:]
                idx = BluesoundPlayer._try_get_index(url, ':')
                if idx > 0:
                    url = url[:idx]
                if url.lower() == stream_url.lower():
                    return item['title']

        items = [x for x in self._capture_items
                 if x['name'] == current_service]
        if len(items) > 0:
            return items[0]['title']

        items = [x for x in self._services_items
                 if x['name'] == current_service]
        if len(items) > 0:
            return items[0]['title']

        if self._status.get('streamUrl', '') != '':
            _LOGGER.debug("Couldn't find source of stream URL: %s",
                          self._status.get('streamUrl', ''))
        return None

    @property
    def supported_features(self):
        """Flag of media commands that are supported."""
        if self._status is None:
            return None

        supported = SUPPORT_CLEAR_PLAYLIST

        if self._status.get('indexing', '0') == '0':
            supported = supported | SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | \
                      SUPPORT_NEXT_TRACK | SUPPORT_PLAY_MEDIA | \
                      SUPPORT_STOP | SUPPORT_PLAY | SUPPORT_SELECT_SOURCE

        current_vol = self.volume_level
        if current_vol is not None and current_vol >= 0:
            supported = supported | SUPPORT_VOLUME_STEP | \
                        SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE

        if self._status.get('canSeek', '') == '1':
            supported = supported | SUPPORT_SEEK

        return supported

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_MODEL: self._model,
            ATTR_MODEL_NAME: self._model_name,
            ATTR_BRAND: self._brand,
        }

    @asyncio.coroutine
    def async_select_source(self, source):
        """Select input source."""
        items = [x for x in self._preset_items if x['title'] == source]

        if len(items) < 1:
            items = [x for x in self._services_items if x['title'] == source]
        if len(items) < 1:
            items = [x for x in self._capture_items if x['title'] == source]

        if len(items) < 1:
            return

        selected_source = items[0]
        url = 'Play?url={}&preset_id&image={}'.format(
            selected_source['url'], selected_source['image'])

        if 'is_raw_url' in selected_source and selected_source['is_raw_url']:
            url = selected_source['url']

        return self.send_bluesound_command(url)

    @asyncio.coroutine
    def async_clear_playlist(self):
        """Clear players playlist."""
        return self.send_bluesound_command('Clear')

    @asyncio.coroutine
    def async_media_next_track(self):
        """Send media_next command to media player."""
        cmd = 'Skip'
        if self._status and 'actions' in self._status:
            for action in self._status['actions']['action']:
                if ('@name' in action and '@url' in action and
                        action['@name'] == 'skip'):
                    cmd = action['@url']

        return self.send_bluesound_command(cmd)

    @asyncio.coroutine
    def async_media_previous_track(self):
        """Send media_previous command to media player."""
        cmd = 'Back'
        if self._status and 'actions' in self._status:
            for action in self._status['actions']['action']:
                if ('@name' in action and '@url' in action and
                        action['@name'] == 'back'):
                    cmd = action['@url']

        return self.send_bluesound_command(cmd)

    @asyncio.coroutine
    def async_media_play(self):
        """Send media_play command to media player."""
        return self.send_bluesound_command('Play')

    @asyncio.coroutine
    def async_media_pause(self):
        """Send media_pause command to media player."""
        return self.send_bluesound_command('Pause')

    @asyncio.coroutine
    def async_media_stop(self):
        """Send stop command."""
        return self.send_bluesound_command('Pause')

    @asyncio.coroutine
    def async_media_seek(self, position):
        """Send media_seek command to media player."""
        return self.send_bluesound_command('Play?seek=' + str(float(position)))

    @asyncio.coroutine
    def async_volume_up(self):
        """Volume up the media player."""
        current_vol = self.volume_level
        if not current_vol or current_vol < 0:
            return
        return self.async_set_volume_level(((current_vol*100)+1)/100)

    @asyncio.coroutine
    def async_volume_down(self):
        """Volume down the media player."""
        current_vol = self.volume_level
        if not current_vol or current_vol < 0:
            return
        return self.async_set_volume_level(((current_vol*100)-1)/100)

    @asyncio.coroutine
    def async_set_volume_level(self, volume):
        """Send volume_up command to media player."""
        if volume < 0:
            volume = 0
        elif volume > 1:
            volume = 1
        return self.send_bluesound_command(
            'Volume?level=' + str(float(volume) * 100))

    @asyncio.coroutine
    def async_mute_volume(self, mute):
        """Send mute command to media player."""
        if mute:
            volume = self.volume_level
            if volume > 0:
                self._lastvol = volume
            return self.send_bluesound_command('Volume?level=0')
        else:
            return self.send_bluesound_command(
                'Volume?level=' + str(float(self._lastvol) * 100))
