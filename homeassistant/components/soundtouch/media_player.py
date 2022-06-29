"""Support for interface with a Bose Soundtouch."""
from __future__ import annotations

from functools import partial
import logging
import re

from libsoundtouch import soundtouch_device
from libsoundtouch.utils import Source
import voluptuous as vol

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.browse_media import (
    async_process_play_media_url,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_START,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    DOMAIN,
    SERVICE_ADD_ZONE_SLAVE,
    SERVICE_CREATE_ZONE,
    SERVICE_PLAY_EVERYWHERE,
    SERVICE_REMOVE_ZONE_SLAVE,
)

_LOGGER = logging.getLogger(__name__)

MAP_STATUS = {
    "PLAY_STATE": STATE_PLAYING,
    "BUFFERING_STATE": STATE_PLAYING,
    "PAUSE_STATE": STATE_PAUSED,
    "STOP_STATE": STATE_OFF,
}

DATA_SOUNDTOUCH = "soundtouch"
ATTR_SOUNDTOUCH_GROUP = "soundtouch_group"
ATTR_SOUNDTOUCH_ZONE = "soundtouch_zone"

SOUNDTOUCH_PLAY_EVERYWHERE = vol.Schema({vol.Required("master"): cv.entity_id})

SOUNDTOUCH_CREATE_ZONE_SCHEMA = vol.Schema(
    {vol.Required("master"): cv.entity_id, vol.Required("slaves"): cv.entity_ids}
)

SOUNDTOUCH_ADD_ZONE_SCHEMA = vol.Schema(
    {vol.Required("master"): cv.entity_id, vol.Required("slaves"): cv.entity_ids}
)

SOUNDTOUCH_REMOVE_ZONE_SCHEMA = vol.Schema(
    {vol.Required("master"): cv.entity_id, vol.Required("slaves"): cv.entity_ids}
)

DEFAULT_NAME = "Bose Soundtouch"
DEFAULT_PORT = 8090

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Bose Soundtouch platform."""
    if DATA_SOUNDTOUCH not in hass.data:
        hass.data[DATA_SOUNDTOUCH] = []

    if discovery_info:
        host = discovery_info["host"]
        port = int(discovery_info["port"])

        # if device already exists by config
        if host in [device.config["host"] for device in hass.data[DATA_SOUNDTOUCH]]:
            return

        remote_config = {"id": "ha.component.soundtouch", "host": host, "port": port}
        bose_soundtouch_entity = SoundTouchDevice(None, remote_config)
        hass.data[DATA_SOUNDTOUCH].append(bose_soundtouch_entity)
        add_entities([bose_soundtouch_entity], True)
    else:
        name = config.get(CONF_NAME)
        remote_config = {
            "id": "ha.component.soundtouch",
            "port": config.get(CONF_PORT),
            "host": config.get(CONF_HOST),
        }
        bose_soundtouch_entity = SoundTouchDevice(name, remote_config)
        hass.data[DATA_SOUNDTOUCH].append(bose_soundtouch_entity)
        add_entities([bose_soundtouch_entity], True)

    def service_handle(service: ServiceCall) -> None:
        """Handle the applying of a service."""
        master_device_id = service.data.get("master")
        slaves_ids = service.data.get("slaves")
        slaves = []
        if slaves_ids:
            slaves = [
                device
                for device in hass.data[DATA_SOUNDTOUCH]
                if device.entity_id in slaves_ids
            ]

        master = next(
            iter(
                [
                    device
                    for device in hass.data[DATA_SOUNDTOUCH]
                    if device.entity_id == master_device_id
                ]
            ),
            None,
        )

        if master is None:
            _LOGGER.warning(
                "Unable to find master with entity_id: %s", str(master_device_id)
            )
            return

        if service.service == SERVICE_PLAY_EVERYWHERE:
            slaves = [
                d for d in hass.data[DATA_SOUNDTOUCH] if d.entity_id != master_device_id
            ]
            master.create_zone(slaves)
        elif service.service == SERVICE_CREATE_ZONE:
            master.create_zone(slaves)
        elif service.service == SERVICE_REMOVE_ZONE_SLAVE:
            master.remove_zone_slave(slaves)
        elif service.service == SERVICE_ADD_ZONE_SLAVE:
            master.add_zone_slave(slaves)

    hass.services.register(
        DOMAIN,
        SERVICE_PLAY_EVERYWHERE,
        service_handle,
        schema=SOUNDTOUCH_PLAY_EVERYWHERE,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_CREATE_ZONE,
        service_handle,
        schema=SOUNDTOUCH_CREATE_ZONE_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_REMOVE_ZONE_SLAVE,
        service_handle,
        schema=SOUNDTOUCH_REMOVE_ZONE_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_ADD_ZONE_SLAVE,
        service_handle,
        schema=SOUNDTOUCH_ADD_ZONE_SCHEMA,
    )


class SoundTouchDevice(MediaPlayerEntity):
    """Representation of a SoundTouch Bose device."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )

    def __init__(self, name, config):
        """Create Soundtouch Entity."""

        self._device = soundtouch_device(config["host"], config["port"])
        if name is None:
            self._name = self._device.config.name
        else:
            self._name = name
        self._status = None
        self._volume = None
        self._config = config
        self._zone = None

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
        self._zone = self.get_zone_info()

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
        if self._status.source == "STANDBY":
            return STATE_OFF

        return MAP_STATUS.get(self._status.play_status, STATE_UNAVAILABLE)

    @property
    def source(self):
        """Name of the current input source."""
        return self._status.source

    @property
    def source_list(self):
        """List of available input sources."""
        return [
            Source.AUX.value,
            Source.BLUETOOTH.value,
        ]

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._volume.muted

    def turn_off(self):
        """Turn off media player."""
        self._device.power_off()

    def turn_on(self):
        """Turn on media player."""
        self._device.power_on()

    def volume_up(self):
        """Volume up the media player."""
        self._device.volume_up()

    def volume_down(self):
        """Volume down media player."""
        self._device.volume_down()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._device.set_volume(int(volume * 100))

    def mute_volume(self, mute):
        """Send mute command."""
        self._device.mute()

    def media_play_pause(self):
        """Simulate play pause media player."""
        self._device.play_pause()

    def media_play(self):
        """Send play command."""
        self._device.play()

    def media_pause(self):
        """Send media pause command to media player."""
        self._device.pause()

    def media_next_track(self):
        """Send next track command."""
        self._device.next_track()

    def media_previous_track(self):
        """Send the previous track command."""
        self._device.previous_track()

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._status.image

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._status.station_name is not None:
            return self._status.station_name
        if self._status.artist is not None:
            return f"{self._status.artist} - {self._status.track}"

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

    async def async_added_to_hass(self):
        """Populate zone info which requires entity_id."""

        @callback
        def async_update_on_start(event):
            """Schedule an update when all platform entities have been added."""
            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, async_update_on_start
        )

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = async_process_play_media_url(self.hass, play_item.url)

        await self.hass.async_add_executor_job(
            partial(self.play_media, media_type, media_id, **kwargs)
        )

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        _LOGGER.debug("Starting media with media_id: %s", media_id)
        if re.match(r"http?://", str(media_id)):
            # URL
            _LOGGER.debug("Playing URL %s", str(media_id))
            self._device.play_url(str(media_id))
        else:
            # Preset
            presets = self._device.presets()
            preset = next(
                iter(
                    [preset for preset in presets if preset.preset_id == str(media_id)]
                ),
                None,
            )
            if preset is not None:
                _LOGGER.debug("Playing preset: %s", preset.name)
                self._device.select_preset(preset)
            else:
                _LOGGER.warning("Unable to find preset with id %s", media_id)

    def select_source(self, source):
        """Select input source."""
        if source == Source.AUX.value:
            _LOGGER.debug("Selecting source AUX")
            self._device.select_source_aux()
        elif source == Source.BLUETOOTH.value:
            _LOGGER.debug("Selecting source Bluetooth")
            self._device.select_source_bluetooth()
        else:
            _LOGGER.warning("Source %s is not supported", source)

    def create_zone(self, slaves):
        """
        Create a zone (multi-room)  and play on selected devices.

        :param slaves: slaves on which to play

        """
        if not slaves:
            _LOGGER.warning("Unable to create zone without slaves")
        else:
            _LOGGER.info("Creating zone with master %s", self._device.config.name)
            self._device.create_zone([slave.device for slave in slaves])

    def remove_zone_slave(self, slaves):
        """
        Remove slave(s) from and existing zone (multi-room).

        Zone must already exist and slaves array can not be empty.
        Note: If removing last slave, the zone will be deleted and you'll have
        to create a new one. You will not be able to add a new slave anymore

        :param slaves: slaves to remove from the zone

        """
        if not slaves:
            _LOGGER.warning("Unable to find slaves to remove")
        else:
            _LOGGER.info(
                "Removing slaves from zone with master %s", self._device.config.name
            )
            # SoundTouch API seems to have a bug and won't remove slaves if there are
            # more than one in the payload. Therefore we have to loop over all slaves
            # and remove them individually
            for slave in slaves:
                # make sure to not try to remove the master (aka current device)
                if slave.entity_id != self.entity_id:
                    self._device.remove_zone_slave([slave.device])

    def add_zone_slave(self, slaves):
        """
        Add slave(s) to and existing zone (multi-room).

        Zone must already exist and slaves array can not be empty.

        :param slaves:slaves to add

        """
        if not slaves:
            _LOGGER.warning("Unable to find slaves to add")
        else:
            _LOGGER.info(
                "Adding slaves to zone with master %s", self._device.config.name
            )
            self._device.add_zone_slave([slave.device for slave in slaves])

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        attributes = {}

        if self._zone and "master" in self._zone:
            attributes[ATTR_SOUNDTOUCH_ZONE] = self._zone
            # Compatibility with how other components expose their groups (like SONOS).
            # First entry is the master, others are slaves
            group_members = [self._zone["master"]] + self._zone["slaves"]
            attributes[ATTR_SOUNDTOUCH_GROUP] = group_members

        return attributes

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(self.hass, media_content_id)

    def get_zone_info(self):
        """Return the current zone info."""
        zone_status = self._device.zone_status()
        if not zone_status:
            return None

        # Due to a bug in the SoundTouch API itself client devices do NOT return their
        # siblings as part of the "slaves" list. Only the master has the full list of
        # slaves for some reason. To compensate for this shortcoming we have to fetch
        # the zone info from the master when the current device is a slave until this is
        # fixed in the SoundTouch API or libsoundtouch, or of course until somebody has a
        # better idea on how to fix this.
        # In addition to this shortcoming, libsoundtouch seems to report the "is_master"
        # property wrong on some slaves, so the only reliable way to detect if the current
        # devices is the master, is by comparing the master_id of the zone with the device_id
        if zone_status.master_id == self._device.config.device_id:
            return self._build_zone_info(self.entity_id, zone_status.slaves)

        # The master device has to be searched by it's ID and not IP since libsoundtouch / BOSE API
        # do not return the IP of the master for some slave objects/responses
        master_instance = self._get_instance_by_id(zone_status.master_id)
        if master_instance is not None:
            master_zone_status = master_instance.device.zone_status()
            return self._build_zone_info(
                master_instance.entity_id, master_zone_status.slaves
            )

        # We should never end up here since this means we haven't found a master device to get the
        # correct zone info from. In this case, assume current device is master
        return self._build_zone_info(self.entity_id, zone_status.slaves)

    def _get_instance_by_ip(self, ip_address):
        """Search and return a SoundTouchDevice instance by it's IP address."""
        for instance in self.hass.data[DATA_SOUNDTOUCH]:
            if instance and instance.config["host"] == ip_address:
                return instance
        return None

    def _get_instance_by_id(self, instance_id):
        """Search and return a SoundTouchDevice instance by it's ID (aka MAC address)."""
        for instance in self.hass.data[DATA_SOUNDTOUCH]:
            if instance and instance.device.config.device_id == instance_id:
                return instance
        return None

    def _build_zone_info(self, master, zone_slaves):
        """Build the exposed zone attributes."""
        slaves = []

        for slave in zone_slaves:
            slave_instance = self._get_instance_by_ip(slave.device_ip)
            if slave_instance and slave_instance.entity_id != master:
                slaves.append(slave_instance.entity_id)

        attributes = {
            "master": master,
            "is_master": master == self.entity_id,
            "slaves": slaves,
        }

        return attributes
