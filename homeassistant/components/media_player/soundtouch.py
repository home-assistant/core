"""Support for interface with a Bose Soundtouch."""
import logging
import xml.etree.ElementTree as ET
from xml.dom import minidom

from os import path
import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP,
    SUPPORT_VOLUME_SET, SUPPORT_TURN_ON, MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    CONF_HOST, CONF_NAME, STATE_OFF, STATE_UNKNOWN, CONF_PORT, STATE_PAUSED,
    STATE_PLAYING, STATE_UNAVAILABLE)

REQUIREMENTS = []

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'media_player'
SERVICE_PLAY_EVERYWHERE = 'soundtouch_play_everywhere'
SERVICE_CREATE_ZONE = 'soundtouch_create_zone'
SERVICE_ADD_ZONE_SLAVE = 'soundtouch_add_zone_slave'
SERVICE_REMOVE_ZONE_SLAVE = 'soundtouch_remove_zone_slave'

SOUNDTOUCH_PLAY_EVERYWHERE = vol.Schema({
    'master': cv.entity_id,
})

SOUNDTOUCH_CREATE_ZONE_SCHEMA = vol.Schema({
    'master': cv.entity_id,
    'slaves': cv.entity_ids
})

SOUNDTOUCH_ADD_ZONE_SCHEMA = vol.Schema({
    'master': cv.entity_id,
    'slaves': cv.entity_ids
})

SOUNDTOUCH_REMOVE_ZONE_SCHEMA = vol.Schema({
    'master': cv.entity_id,
    'slaves': cv.entity_ids
})

DEFAULT_NAME = 'Bose Soundtouch'
DEFAULT_PORT = 8090

DEVICES = []

SUPPORT_SOUNDTOUCH = SUPPORT_PAUSE | SUPPORT_VOLUME_STEP | \
                     SUPPORT_VOLUME_MUTE | SUPPORT_PREVIOUS_TRACK | \
                     SUPPORT_NEXT_TRACK | SUPPORT_TURN_OFF | \
                     SUPPORT_VOLUME_SET | SUPPORT_TURN_ON

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Bose Soundtouch platform."""
    name = config.get(CONF_NAME)

    remote_config = {
        'name': 'HomeAssistant',
        'description': config.get(CONF_NAME),
        'id': 'ha.component.soundtouch',
        'port': config.get(CONF_PORT),
        'host': config.get(CONF_HOST)
    }

    soundtouch_device = SoundTouchDevice(name, remote_config)
    DEVICES.append(soundtouch_device)
    add_devices([soundtouch_device])

    descriptions = load_yaml_config_file(
        path.join(path.dirname(__file__), 'services.yaml'))

    hass.services.register(DOMAIN, SERVICE_PLAY_EVERYWHERE,
                           play_everywhere_service,
                           descriptions.get(SERVICE_PLAY_EVERYWHERE),
                           schema=SOUNDTOUCH_PLAY_EVERYWHERE)
    hass.services.register(DOMAIN, SERVICE_CREATE_ZONE,
                           create_zone_service,
                           descriptions.get(SERVICE_CREATE_ZONE),
                           schema=SOUNDTOUCH_CREATE_ZONE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_REMOVE_ZONE_SLAVE,
                           remove_zone_slave,
                           descriptions.get(SERVICE_REMOVE_ZONE_SLAVE),
                           schema=SOUNDTOUCH_REMOVE_ZONE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_ADD_ZONE_SLAVE,
                           add_zone_slave,
                           descriptions.get(SERVICE_ADD_ZONE_SLAVE),
                           schema=SOUNDTOUCH_ADD_ZONE_SCHEMA)


def play_everywhere_service(service):
    """
    Create a zone (multi-room)  and play on all devices.

    :param service: Home Assistant service with 'master' data set

    :Example:

    - service: media_player.soundtouch_play_everywhere
      data:
        master: media_player.soundtouch_living_room

    """
    master_device_id = service.data.get('master')
    slaves = [d for d in DEVICES if d.entity_id != master_device_id]
    masters = [device for device in DEVICES
               if device.entity_id == master_device_id]
    try:
        request_body = _create_zone(masters, slaves)
        _LOGGER.info("Playing everywhere with master device %s",
                     masters[0].entity_id)
        requests.post("http://" + masters[0].config["host"] + ":" + str(
            masters[0].config["port"]) + "/setZone",
                      request_body)
    except SoundtouchException as soundtouch_exception:
        _LOGGER.error(str(soundtouch_exception))


def create_zone_service(service):
    """
    Create a zone (multi-room) on a master and play on specified slaves.

    At least one master and one slave must be specified

    :param service: Home Assistant service with 'master' and 'slaves' data set

    :Example:

    - service: media_player.soundtouch_create_zone
      data:
        master: media_player.soundtouch_living_room
        slaves:
          - media_player.soundtouch_room
          - media_player.soundtouch_kitchen

    """
    master_device_id = service.data.get('master')
    slaves_ids = service.data.get('slaves')
    slaves = [device for device in DEVICES if device.entity_id in slaves_ids]
    masters = [device for device in DEVICES
               if device.entity_id == master_device_id]
    try:
        request_body = _create_zone(masters, slaves)
        _LOGGER.info("Creating multi-room zone with master device %s",
                     masters[0].entity_id)
        requests.post("http://" + masters[0].config["host"] + ":" + str(
            masters[0].config["port"]) + "/setZone",
                      request_body)
    except SoundtouchException as soundtouch_exception:
        _LOGGER.error(str(soundtouch_exception))


def add_zone_slave(service):
    """
    Add slave(s) to and existing zone (multi-room).

    Zone must already exist and slaves array can not be empty.

    :param service: Home Assistant service with 'master' and 'slaves' data set

    :Example:

    - service: media_player.soundtouch_add_zone_slave
      data:
        master: media_player.soundtouch_living_room
        slaves:
          - media_player.soundtouch_room

    """
    master_device_id = service.data.get('master')
    slaves_ids = service.data.get('slaves')
    slaves = [device for device in DEVICES if device.entity_id in slaves_ids]
    masters = [device for device in DEVICES
               if device.entity_id == master_device_id]
    try:
        request_body = _get_zone_request_body(masters, slaves)
        _LOGGER.info("Adding slaves to multi-room zone with master device %s",
                     masters[0].entity_id)
        requests.post(
            "http://" + masters[0].config["host"] + ":" + str(
                masters[0].config["port"]) + "/addZoneSlave",
            request_body)
    except SoundtouchException as soundtouch_exception:
        _LOGGER.error(str(soundtouch_exception))


def remove_zone_slave(service):
    """
    Remove slave(s) from and existing zone (multi-room).

    Zone must already exist and slaves array can not be empty.
    Note: If removing last slave, the zone will be deleted and you'll have to
    create a new one. You will not be able to add a new slave anymore

    :param service: Home Assistant service with 'master' and 'slaves' data set

    :Example:

    - service: media_player.soundtouch_remove_zone_slave
      data:
        master: media_player.soundtouch_living_room
        slaves:
          - media_player.soundtouch_room

    """
    master_device_id = service.data.get('master')
    slaves_ids = service.data.get('slaves')
    slaves = [device for device in DEVICES if device.entity_id in slaves_ids]
    masters = [device for device in DEVICES
               if device.entity_id == master_device_id]
    try:
        request_body = _get_zone_request_body(masters, slaves)
        _LOGGER.info("Removing slaves from multi-room zone with master " +
                     "device %s", masters[0].entity_id)
        requests.post(
            "http://" + masters[0].config["host"] + ":" + str(
                masters[0].config["port"]) + "/removeZoneSlave",
            request_body)
    except SoundtouchException as spundtouch_exception:
        _LOGGER.error(str(spundtouch_exception))


def _get_zone_request_body(masters, slaves):
    if len(masters) < 1:
        raise MasterNotFoundException()
    if len(slaves) <= 0:
        raise NoSlavesException()
    master_device_info = _get_device_info(masters[0])
    request_body = '<zone master="%s">' % (master_device_info["device_id"])
    for slave in slaves:
        slave_info = _get_device_info(slave)
        request_body += '<member ipaddress="%s">%s</member>' % (
            slave_info["device_ip"], slave_info["device_id"])
    request_body += '</zone>'
    return request_body


def _create_zone(masters, slaves):
    if len(masters) < 1:
        raise MasterNotFoundException()
    if len(slaves) <= 0:
        raise NoSlavesException()
    master_device_info = _get_device_info(masters[0])
    request_body = '<zone master="%s" senderIPAddress="%s">' % (
        master_device_info["device_id"], master_device_info["device_ip"])
    for slave in slaves:
        slave_info = _get_device_info(slave)
        request_body += '<member ipaddress="%s">%s</member>' % (
            slave_info["device_ip"], slave_info["device_id"])
    request_body += '</zone>'
    return request_body


def _get_device_info(device):
    response = requests.get(
        "http://" + device.config["host"] + ":" + str(device.config["port"]) +
        "/info")
    dom = minidom.parseString(response.text)
    device_id = dom.getElementsByTagName("info")[0].attributes[
        "deviceID"].value
    device_name = dom.getElementsByTagName("name")[0].firstChild.nodeValue
    device_type = dom.getElementsByTagName("type")[0].firstChild.nodeValue
    device_ip = dom.getElementsByTagName("ipAddress")[0].firstChild.nodeValue
    return {
        "device_id": device_id,
        "device_name": device_name,
        "device_type": device_type,
        "device_ip": device_ip,
        "device_port": device.config["port"]
    }


class SoundTouchDevice(MediaPlayerDevice):
    """Representation of a SoundTouch Bose devicce."""

    def __init__(self, name, config):
        """Create Soundtouch Entity."""
        self._name = name
        self._muted = False
        self._playing = True
        self._state = STATE_UNKNOWN
        self._remote = None
        self._config = config
        self._media_title = None
        self._media_artist = None
        self._media_album_name = None
        self._media_image_url = None
        self._media_duration = None
        self._media_track = None

    def _reset_properties(self):
        self._media_title = None
        self._media_artist = None
        self._media_album_name = None
        self._media_image_url = None
        self._media_duration = None
        self._media_track = None

    @property
    def config(self):
        """Return specific soundtouch configuration."""
        return self._config

    def _set_image_url(self, source, doc):
        art_status = None
        if source in ["SPOTIFY", "INTERNET_RADIO", "STORED_MUSIC"]:
            art_status = doc.getElementsByTagName("art")[0].attributes[
                "artImageStatus"].value
        if art_status == "IMAGE_PRESENT":
            self._media_image_url = \
                doc.getElementsByTagName("art")[0].firstChild.nodeValue
        else:
            self._media_image_url = None

    def _set_media_album(self, source, doc):
        if source in ['SPOTIFY', 'STORED_MUSIC']:
            self._media_album_name =\
                doc.getElementsByTagName("album")[0].firstChild.nodeValue
        else:
            self._media_album_name = None

    def _set_media_artist(self, source, doc):
        if source in ['SPOTIFY', 'STORED_MUSIC']:
            self._media_artist =\
                doc.getElementsByTagName("artist")[0].firstChild.nodeValue
        else:
            self._media_artist = None

    def _set_media_track(self, source, doc):
        if source in ['SPOTIFY', 'STORED_MUSIC']:
            self._media_track = \
                doc.getElementsByTagName("track")[0].firstChild.nodeValue
        else:
            self._media_track = None

    def _set_media_title(self, source, doc):
        if source in ['SPOTIFY', 'STORED_MUSIC']:
            self._media_title = self.media_artist + " - " + self.media_track
        elif source == 'INTERNET_RADIO':
            self._media_title = doc.getElementsByTagName("stationName")[
                0].firstChild.nodeValue

    def _set_media_duration(self, source, doc):
        if source in ['SPOTIFY', 'STORED_MUSIC']:
            self._media_duration = \
                int(doc.getElementsByTagName("time")[0].attributes[
                    "total"].value)
        else:
            self._media_duration = None

    def update(self):
        """Retrieve the latest data."""
        doc = self._get_status()
        source = doc.getElementsByTagName("ContentItem")[0].attributes[
            "source"].value
        if source == 'STANDBY':
            self._state = STATE_OFF
            self._reset_properties()
        elif source == 'INVALID_SOURCE':
            self._state = STATE_UNAVAILABLE
            self._reset_properties()
        else:
            status = doc.getElementsByTagName("playStatus")[
                0].firstChild.nodeValue
            if status == "PLAY_STATE":
                self._state = STATE_PLAYING
            elif status == "PAUSE_STATE":
                self._state = STATE_PAUSED
            else:
                self._state = STATE_UNKNOWN

            if self._state in [STATE_PLAYING, STATE_PAUSED]:
                self._set_image_url(source, doc)
                self._set_media_album(source, doc)
                self._set_media_artist(source, doc)
                self._set_media_track(source, doc)
                self._set_media_title(source, doc)
                self._set_media_duration(source, doc)

    def _get_status(self):
        response = requests.get(
            'http://' + self._config['host'] + ":" + str(self._config['port'])
            + '/now_playing')
        doc = minidom.parseString(response.text)
        return doc

    def _send_key(self, key):
        action = '/key'
        press = '<key state="press" sender="Gabbo">%s</key>' % key
        release = '<key state="release" sender="Gabbo">%s</key>' % key
        requests.post('http://' + self._config['host'] + ":" +
                      str(self._config['port']) + action, press)
        requests.post('http://' + self._config['host'] + ":" +
                      str(self._config['port']) + action, release)

    def _get_volume(self):
        action = '/volume'
        response = requests.get(
            'http://' + self._config['host'] + ":" + str(self._config['port'])
            + action)
        doc = minidom.parseString(response.text)
        return int(doc.getElementsByTagName("actualvolume")[
            0].firstChild.nodeValue)

    def _set_volume(self, volume):
        action = '/volume'
        volume = '<volume>%s</volume>' % volume
        requests.post('http://' + self._config['host'] + ":" +
                      str(self._config['port']) + action, volume)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._get_volume() / 100

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self.volume_level == 0.0

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_SOUNDTOUCH

    def turn_off(self):
        """Turn off media player."""
        state = self.state
        if state in [STATE_PLAYING, STATE_PAUSED]:
            _LOGGER.info("Turning off device " + self.entity_id)
            self._send_key('POWER')
        else:
            _LOGGER.warning(
                "Unable to turn off Soundtouch device " +
                self.entity_id + " because it is already in standby")

    def turn_on(self):
        """Turn the media player on."""
        state = self.state
        if state in [STATE_OFF]:
            _LOGGER.info("Turning on device " + self.entity_id)
            self._send_key('POWER')
        else:
            _LOGGER.warning(
                "Unable to turn on Soundtouch device " +
                self.entity_id + " because it is already playing")

    def volume_up(self):
        """Volume up the media player."""
        current_volume = self._get_volume()
        self._set_volume(current_volume + 5)

    def volume_down(self):
        """Volume down media player."""
        current_volume = self._get_volume()
        self._set_volume(current_volume - 5)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._set_volume(int(volume * 100))

    def mute_volume(self, mute):
        """Send mute command."""
        self._send_key('MUTE')

    def media_play_pause(self):
        """Simulate play pause media player."""
        state = self.state
        if state == STATE_PLAYING:
            self.media_pause()
        elif state == STATE_PAUSED:
            self.media_play()

    def media_play(self):
        """Send play command."""
        self._playing = True
        self._send_key('PLAY')

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self._send_key('PAUSE')

    def media_next_track(self):
        """Send next track command."""
        self._send_key('NEXT_TRACK')

    def media_previous_track(self):
        """Send the previous track command."""
        self._send_key('PREV_TRACK')

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._media_image_url

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._media_title

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._media_duration

    @property
    def media_artist(self):
        """Artist of current playing media."""
        return self._media_artist

    @property
    def media_track(self):
        """Artist of current playing media."""
        return self._media_track

    @property
    def media_album_name(self):
        """Album name of current playing media."""
        return self._media_album_name

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        _LOGGER.info("Starting media with media_id:" + str(media_id))
        xpath = "./preset[@id='%s']" % str(media_id)
        key = '/presets'
        response = requests.get(
            'http://' + self._config['host'] + ":" + str(self._config[
                'port']) + key)
        tree = ET.ElementTree(ET.fromstring(response.text))
        preset = tree.find(xpath)
        if preset is not None:
            content = ET.tostring(preset[0]).decode('utf-8')
            requests.post(
                'http://' + self._config['host'] + ":" +
                str(self._config['port']) + '/select',
                content)
        else:
            _LOGGER.warning("Unable to find preset with id " + str(media_id))


class SoundtouchException(Exception):
    """Parent Soundtouch Exception."""

    def __init__(self):
        """Soundtouch Exception."""
        super(SoundtouchException, self).__init__()


class MasterNotFoundException(SoundtouchException):
    """Exception while managing multi-room action without valid master."""

    def __init__(self):
        """MasterNotFoundException."""
        super(MasterNotFoundException, self).__init__()

    def __str__(self):
        """Return str(self)."""
        return "Unable to find Master"


class NoSlavesException(SoundtouchException):
    """Exception while managing multi-room actions without valid slaves."""

    def __init__(self):
        """NoSlavesException."""
        super(NoSlavesException, self).__init__()

    def __str__(self):
        """Return str(self)."""
        return "No slaves available"
