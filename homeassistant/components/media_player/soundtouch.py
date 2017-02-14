"""Support for interface with a Bose Soundtouch."""
import logging

from os import path
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP,
    SUPPORT_VOLUME_SET, SUPPORT_TURN_ON, SUPPORT_PLAY, MediaPlayerDevice,
    PLATFORM_SCHEMA)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (CONF_HOST, CONF_NAME, STATE_OFF, CONF_PORT,
                                 STATE_PAUSED, STATE_PLAYING,
                                 STATE_UNAVAILABLE)

REQUIREMENTS = ['libsoundtouch==0.1.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'media_player'
SERVICE_PLAY_EVERYWHERE = 'soundtouch_play_everywhere'
SERVICE_CREATE_ZONE = 'soundtouch_create_zone'
SERVICE_ADD_ZONE_SLAVE = 'soundtouch_add_zone_slave'
SERVICE_REMOVE_ZONE_SLAVE = 'soundtouch_remove_zone_slave'

MAP_STATUS = {
    "PLAY_STATE": STATE_PLAYING,
    "BUFFERING_STATE": STATE_PLAYING,
    "PAUSE_STATE": STATE_PAUSED,
    "STOp_STATE": STATE_OFF
}

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
    SUPPORT_VOLUME_SET | SUPPORT_TURN_ON | SUPPORT_PLAY

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
    master = next([device for device in DEVICES if
                   device.entity_id == master_device_id].__iter__(), None)
    if master is None:
        _LOGGER.warning(
            "Unable to find master with entity_id:" + str(master_device_id))
    elif not slaves:
        _LOGGER.warning("Unable to create zone without slaves")
    else:
        _LOGGER.info(
            "Creating zone with master " + str(master.device.config.name))
        master.device.create_zone([slave.device for slave in slaves])


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
    master = next([device for device in DEVICES if
                   device.entity_id == master_device_id].__iter__(), None)
    if master is None:
        _LOGGER.warning(
            "Unable to find master with entity_id:" + master_device_id)
    elif not slaves:
        _LOGGER.warning("Unable to create zone without slaves")
    else:
        _LOGGER.info(
            "Creating zone with master " + str(master.device.config.name))
        master.device.create_zone([slave.device for slave in slaves])


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
    master = next([device for device in DEVICES if
                   device.entity_id == master_device_id].__iter__(), None)
    if master is None:
        _LOGGER.warning(
            "Unable to find master with entity_id:" + str(master_device_id))
    elif not slaves:
        _LOGGER.warning("Unable to find slaves to add")
    else:
        _LOGGER.info(
            "Adding slaves to zone with master " + str(
                master.device.config.name))
        master.device.add_zone_slave([slave.device for slave in slaves])


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
    master = next([device for device in DEVICES if
                   device.entity_id == master_device_id].__iter__(), None)
    if master is None:
        _LOGGER.warning(
            "Unable to find master with entity_id:" + master_device_id)
    elif not slaves:
        _LOGGER.warning("Unable to find slaves to remove")
    else:
        _LOGGER.info("Removing slaves from zone with master " +
                     str(master.device.config.name))
        master.device.remove_zone_slave([slave.device for slave in slaves])


class SoundTouchDevice(MediaPlayerDevice):
    """Representation of a SoundTouch Bose device."""

    def __init__(self, name, config):
        """Create Soundtouch Entity."""
        from libsoundtouch import soundtouch_device
        self._name = name
        self._device = soundtouch_device(config['host'], config['port'])
        self._status = self._device.status()
        self._volume = self._device.volume()
        self._config = config

    @property
    def config(self):
        """Return specific soundtouch configuration."""
        return self._config

    @property
    def device(self):
        """Return Soundtouch device."""
        return self._device

    def update(self):
        """Retrieve the latest data."""
        self._status = self._device.status()
        self._volume = self._device.volume()

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume.actual / 100

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._status.source == 'STANDBY':
            return STATE_OFF
        else:
            return MAP_STATUS.get(self._status.play_status, STATE_UNAVAILABLE)

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._volume.muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_SOUNDTOUCH

    def turn_off(self):
        """Turn off media player."""
        self._device.power_off()
        self._status = self._device.status()

    def turn_on(self):
        """Turn the media player on."""
        self._device.power_on()
        self._status = self._device.status()

    def volume_up(self):
        """Volume up the media player."""
        self._device.volume_up()
        self._volume = self._device.volume()

    def volume_down(self):
        """Volume down media player."""
        self._device.volume_down()
        self._volume = self._device.volume()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._device.set_volume(int(volume * 100))
        self._volume = self._device.volume()

    def mute_volume(self, mute):
        """Send mute command."""
        self._device.mute()
        self._volume = self._device.volume()

    def media_play_pause(self):
        """Simulate play pause media player."""
        self._device.play_pause()
        self._status = self._device.status()

    def media_play(self):
        """Send play command."""
        self._device.play()
        self._status = self._device.status()

    def media_pause(self):
        """Send media pause command to media player."""
        self._device.pause()
        self._status = self._device.status()

    def media_next_track(self):
        """Send next track command."""
        self._device.next_track()
        self._status = self._device.status()

    def media_previous_track(self):
        """Send the previous track command."""
        self._device.previous_track()
        self._status = self._device.status()

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._status.image

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._status.station_name is not None:
            return self._status.station_name
        elif self._status.artist is not None:
            return self._status.artist + " - " + self._status.track
        else:
            return None

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._status.duration

    @property
    def media_artist(self):
        """Artist of current playing media."""
        return self._status.artist

    @property
    def media_track(self):
        """Artist of current playing media."""
        return self._status.track

    @property
    def media_album_name(self):
        """Album name of current playing media."""
        return self._status.album

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        _LOGGER.info("Starting media with media_id:" + str(media_id))
        presets = self._device.presets()
        preset = next([preset for preset in presets if
                       preset.preset_id == str(media_id)].__iter__(), None)
        if preset is not None:
            _LOGGER.info("Playing preset: " + preset.name)
            self._device.select_preset(preset)
        else:
            _LOGGER.warning("Unable to find preset with id " + str(media_id))
