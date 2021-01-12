"""Support for Denon AVR receivers using their HTTP interface."""
from typing import Sequence

from pyavreceiver.receiver import AVReceiver
from pyavreceiver.zone import Zone

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    DOMAIN,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON

from .const import (
    CONF_ZONE1,
    DOMAIN as AVRECEIVER_DOMAIN,
    SIGNAL_AVR_UPDATED,
    THREE_DECIBELS,
)

BASE_SUPPORTED_FEATURES = (
    SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
)


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities):
    """Add media players for a config entry."""
    zones = hass.data[AVRECEIVER_DOMAIN][entry.entry_id][DOMAIN]
    entities = []
    for name, zone in zones.items():
        await zone.update_all()
        if name == CONF_ZONE1:
            entities.append(AVRMainZone(zone, name))
        else:
            entities.append(AVRZone(zone, name))
    async_add_entities(entities)


class AVRZone(MediaPlayerEntity):
    """Representation of an AV Receiver zone."""

    def __init__(self, zone: Zone, zone_name: str):
        """Initialize the device."""
        self._zone = zone
        self._zone_name = zone_name
        self._avr = zone._avr  # type: AVReceiver
        self._signals = []
        self._supported_features_base = BASE_SUPPORTED_FEATURES
        self._volume_multiplier = (
            self._zone.max_volume or 0 - self._zone.min_volume or -80
        )

    async def _avr_updated(self):
        """Handle avr attribute updated."""
        await self.async_update_ha_state(True)

    async def async_added_to_hass(self):
        """Device added to hass."""
        # Update state when avr changes
        self._signals.append(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_AVR_UPDATED, self._avr_updated
            )
        )

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return self._avr.connection_state == "connected"

    @property
    def device_info(self) -> dict:
        """Get attributes about the device."""
        return {
            "identifiers": {(AVRECEIVER_DOMAIN, self._avr.host)},
            "name": self._avr.friendly_name,
            "model": self._avr.model,
            "manufacturer": self._avr.manufacturer,
        }

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self._avr.friendly_name} {self._zone_name}"

    @property
    def state(self):
        """Return the state of the device."""
        return STATE_ON if self._zone.power else STATE_OFF

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self._zone.mute

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return (
            f"{AVRECEIVER_DOMAIN}-"
            f"{self._avr.serial_number or self._avr.mac or self._avr.host}-"
            f"{self._zone_name}"
        )

    @property
    def volume_level(self) -> float:
        """Volume level of the media player (0..1)."""
        return float(self._volume_multiplier + self._zone.volume) / (
            self._volume_multiplier
        )

    @property
    def source(self) -> str:
        """Return the current input source."""
        return self._zone.source

    @property
    def source_list(self) -> Sequence[str]:
        """Return a list of available input sources."""
        return self._zone.source_list

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return self._supported_features_base

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return self._zone.state

    @property
    def should_poll(self) -> bool:
        """No polling needed for this device."""
        return False

    async def async_select_source(self, source):
        """Select input source."""
        return await self._zone.set_source(source)

    async def async_turn_on(self):
        """Turn on media player."""
        await self._zone.set_power(True)

    async def async_turn_off(self):
        """Turn off media player."""
        await self._zone.set_power(False)

    async def async_volume_up(self):
        """Volume up the media player."""
        await self._zone.set_volume(self._zone.volume + THREE_DECIBELS)

    async def async_volume_down(self):
        """Volume down media player."""
        await self._zone.set_volume(self._zone.volume - THREE_DECIBELS)

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        volume_denon = float(
            (volume * self._volume_multiplier) - self._volume_multiplier
        )
        await self._zone.set_volume(volume_denon)

    async def async_mute_volume(self, mute):
        """Send mute command."""
        await self._zone.set_mute(mute)


class AVRMainZone(AVRZone):
    """Representation of an AV Receiver main zone."""

    @property
    def sound_mode(self):
        """Return the current matched sound mode."""
        return self._zone.soundmode

    @property
    def sound_mode_list(self) -> Sequence[str]:
        """Return a list of available sound modes."""
        return self._zone.sound_mode_list

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return self._supported_features_base | SUPPORT_SELECT_SOUND_MODE

    async def async_select_sound_mode(self, sound_mode):
        """Select sound mode."""
        return await self._zone.set_soundmode(sound_mode)
