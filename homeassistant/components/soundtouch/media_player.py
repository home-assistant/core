"""Support for interface with a Bose SoundTouch."""

from __future__ import annotations

from functools import partial
import logging
from typing import Any

from libsoundtouch.device import SoundTouchDevice
from libsoundtouch.utils import Source

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MAP_STATUS = {
    "PLAY_STATE": MediaPlayerState.PLAYING,
    "BUFFERING_STATE": MediaPlayerState.PLAYING,
    "PAUSE_STATE": MediaPlayerState.PAUSED,
    "STOP_STATE": MediaPlayerState.OFF,
}

ATTR_SOUNDTOUCH_GROUP = "soundtouch_group"
ATTR_SOUNDTOUCH_ZONE = "soundtouch_zone"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bose SoundTouch media player based on a config entry."""
    device = hass.data[DOMAIN][entry.entry_id].device
    media_player = SoundTouchMediaPlayer(device)

    async_add_entities([media_player], True)

    hass.data[DOMAIN][entry.entry_id].media_player = media_player


class SoundTouchMediaPlayer(MediaPlayerEntity):
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
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_has_entity_name = True
    _attr_name = None
    _attr_source_list = [
        Source.AUX.value,
        Source.BLUETOOTH.value,
    ]

    def __init__(self, device: SoundTouchDevice) -> None:
        """Create SoundTouch media player entity."""

        self._device = device

        self._attr_unique_id = device.config.device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.config.device_id)},
            connections={
                (CONNECTION_NETWORK_MAC, format_mac(device.config.mac_address))
            },
            manufacturer="Bose Corporation",
            model=device.config.type,
            name=device.config.name,
        )

        self._status = None
        self._volume = None
        self._zone = None

    @property
    def device(self):
        """Return SoundTouch device."""
        return self._device

    def update(self) -> None:
        """Retrieve the latest data."""
        self._status = self._device.status()
        self._volume = self._device.volume()
        self._zone = self.get_zone_info()

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume.actual / 100

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if self._status is None or self._status.source == "STANDBY":
            return MediaPlayerState.OFF

        if self._status.source == "INVALID_SOURCE":
            return None

        return MAP_STATUS.get(self._status.play_status)

    @property
    def source(self):
        """Name of the current input source."""
        return self._status.source

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._volume.muted

    def turn_off(self) -> None:
        """Turn off media player."""
        self._device.power_off()

    def turn_on(self) -> None:
        """Turn on media player."""
        self._device.power_on()

    def volume_up(self) -> None:
        """Volume up the media player."""
        self._device.volume_up()

    def volume_down(self) -> None:
        """Volume down media player."""
        self._device.volume_down()

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._device.set_volume(int(volume * 100))

    def mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        self._device.mute()

    def media_play_pause(self) -> None:
        """Simulate play pause media player."""
        self._device.play_pause()

    def media_play(self) -> None:
        """Send play command."""
        self._device.play()

    def media_pause(self) -> None:
        """Send media pause command to media player."""
        self._device.pause()

    def media_next_track(self) -> None:
        """Send next track command."""
        self._device.next_track()

    def media_previous_track(self) -> None:
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

    async def async_added_to_hass(self) -> None:
        """Populate zone info which requires entity_id."""

        @callback
        def async_update_on_start(event):
            """Schedule an update when all platform entities have been added."""
            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, async_update_on_start
        )

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = async_process_play_media_url(self.hass, play_item.url)

        await self.hass.async_add_executor_job(
            partial(self.play_media, media_type, media_id, **kwargs)
        )

    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        _LOGGER.debug("Starting media with media_id: %s", media_id)
        if str(media_id).lower().startswith("http://"):  # no https support
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

    def select_source(self, source: str) -> None:
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
        """Create a zone (multi-room)  and play on selected devices.

        :param slaves: slaves on which to play

        """
        if not slaves:
            _LOGGER.warning("Unable to create zone without slaves")
        else:
            _LOGGER.debug("Creating zone with master %s", self._device.config.name)
            self._device.create_zone([slave.device for slave in slaves])

    def remove_zone_slave(self, slaves):
        """Remove slave(s) from and existing zone (multi-room).

        Zone must already exist and slaves array cannot be empty.
        Note: If removing last slave, the zone will be deleted and you'll have
        to create a new one. You will not be able to add a new slave anymore

        :param slaves: slaves to remove from the zone

        """
        if not slaves:
            _LOGGER.warning("Unable to find slaves to remove")
        else:
            _LOGGER.debug(
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
        """Add slave(s) to and existing zone (multi-room).

        Zone must already exist and slaves array cannot be empty.

        :param slaves:slaves to add

        """
        if not slaves:
            _LOGGER.warning("Unable to find slaves to add")
        else:
            _LOGGER.debug(
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

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(self.hass, media_content_id)

    def get_zone_info(self):
        """Return the current zone info."""
        zone_status = self._device.zone_status()
        if not zone_status:
            return None

        # Client devices do NOT return their siblings as part of the "slaves" list.
        # Only the master has the full list of slaves. To compensate for this
        # shortcoming we have to fetch the zone info from the master when the current
        # device is a slave.
        # In addition to this shortcoming, libsoundtouch seems to report the "is_master"
        # property wrong on some slaves, so the only reliable way to detect
        # if the current devices is the master, is by comparing the master_id
        # of the zone with the device_id.
        if zone_status.master_id == self._device.config.device_id:
            return self._build_zone_info(self.entity_id, zone_status.slaves)

        # The master device has to be searched by it's ID and not IP since
        # libsoundtouch / BOSE API do not return the IP of the master
        # for some slave objects/responses
        master_instance = self._get_instance_by_id(zone_status.master_id)
        if master_instance is not None:
            master_zone_status = master_instance.device.zone_status()
            return self._build_zone_info(
                master_instance.entity_id, master_zone_status.slaves
            )

        # We should never end up here since this means we haven't found a master
        # device to get the correct zone info from. In this case,
        # assume current device is master
        return self._build_zone_info(self.entity_id, zone_status.slaves)

    def _get_instance_by_ip(self, ip_address):
        """Search and return a SoundTouchDevice instance by it's IP address."""
        for data in self.hass.data[DOMAIN].values():
            if data.device.config.device_ip == ip_address:
                return data.media_player
        return None

    def _get_instance_by_id(self, instance_id):
        """Search and return a SoundTouchDevice instance by it's ID (aka MAC address)."""
        for data in self.hass.data[DOMAIN].values():
            if data.device.config.device_id == instance_id:
                return data.media_player
        return None

    def _build_zone_info(self, master, zone_slaves):
        """Build the exposed zone attributes."""
        slaves = []

        for slave in zone_slaves:
            slave_instance = self._get_instance_by_ip(slave.device_ip)
            if slave_instance and slave_instance.entity_id != master:
                slaves.append(slave_instance.entity_id)

        return {
            "master": master,
            "is_master": master == self.entity_id,
            "slaves": slaves,
        }
