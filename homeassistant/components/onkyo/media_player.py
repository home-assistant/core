"""Support for Onkyo Network Receivers and Processors."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    ATTR_AUDIO_INFORMATION,
    ATTR_HDMI_OUTPUT,
    ATTR_PRESET,
    ATTR_VIDEO_INFORMATION,
    ATTR_VIDEO_OUT,
    CONF_MAX_VOLUME,
    CONF_RECEIVER,
    CONF_SOURCES,
    DEFAULT_MAX_VOLUME,
    DEFAULT_SOURCES,
    DOMAIN,
    SELECT_HDMI_OUTPUT_ACCEPTED_VALUES,
    SERVICE_SELECT_HDMI_OUTPUT,
    SOUND_MODE_MAPPING,
)
from .receiver import OnkyoNetworkReceiver, ReceiverZone


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up MediaPlayer platform for passed config_entry."""
    receiver: OnkyoNetworkReceiver = hass.data[DOMAIN][config_entry.entry_id][
        CONF_RECEIVER
    ]

    max_volume: int = config_entry.options.get(CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME)

    source_mapping: dict[str, str] = config_entry.options.get(
        CONF_SOURCES, DEFAULT_SOURCES
    )

    new_zones: list[OnkyoMediaPlayer] = []
    for zone in receiver.zones.values():
        zone_entity = OnkyoMediaPlayer(zone, max_volume, source_mapping)
        new_zones.append(zone_entity)

    # Register additional services
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SELECT_HDMI_OUTPUT,
        {vol.Required(ATTR_HDMI_OUTPUT): vol.In(SELECT_HDMI_OUTPUT_ACCEPTED_VALUES)},
        "async_select_output",
    )

    # Add all new zones to HA.
    if new_zones:
        async_add_entities(new_zones)


class OnkyoMediaPlayer(MediaPlayerEntity):
    """MediaPlayer entity for Onkyo network receiver zone."""

    should_poll: bool = False

    def __init__(
        self,
        receiver_zone: ReceiverZone,
        max_volume: int,
        source_mapping: dict[str, str],
    ) -> None:
        """Initialize the MediaPlayer."""
        self._receiver_zone: ReceiverZone = receiver_zone
        self._max_volume: int = max_volume
        self._source_list: list[str] = list(source_mapping.values())
        self._source_mapping: dict[str, str] = source_mapping
        self._reverse_source_mapping: dict[str, str] = {
            value: key for key, value in source_mapping.items()
        }

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self._receiver_zone.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._receiver_zone.remove_callback(self.async_write_ha_state)

    @property
    def unique_id(self) -> str:
        """Return Unique ID string."""
        return f"{self._receiver_zone.zone_identifier}_media_player"

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        return self._receiver_zone.supported_features

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._receiver_zone.receiver.identifier)},
            "name": self._receiver_zone.receiver.name,
            "model": self._receiver_zone.receiver.name,
            "manufacturer": self._receiver_zone.receiver.manufacturer,
        }

    @property
    def name(self) -> str:
        """Return the name of the receiver zone."""
        return self._receiver_zone.name

    @property
    def available(self) -> bool:
        """Return True if receiver is online."""
        return self._receiver_zone.receiver.online

    @property
    def state(self) -> str:
        """Return state of power on/off."""
        return self._receiver_zone.powerstate

    @property
    def is_volume_muted(self) -> bool:
        """Return boolean reflecting mute state of device."""
        return self._receiver_zone.muted

    @property
    def volume_level(self) -> float:
        """Return volume level from 0 to 1."""
        return min(self._receiver_zone.volume / self._max_volume, 1)

    @property
    def source(self) -> str:
        """Return currently selected input."""
        return self._parse_unmapped_source(self._receiver_zone.source)

    @property
    def source_list(self) -> list[str]:
        """Return all active, configured inputs."""
        return self._source_list

    @property
    def sound_mode(self) -> str | None:
        """Return the current sound mode."""
        return self._receiver_zone.sound_mode

    @property
    def sound_mode_list(self) -> list[str]:
        """Return a list of available sound modes."""
        return list(SOUND_MODE_MAPPING)

    @property
    def extra_state_attributes(self) -> dict[str, str | dict[str, str] | None]:
        """Return device specific state attributes."""
        return (
            {
                ATTR_PRESET: self._receiver_zone.preset,
                ATTR_VIDEO_OUT: self._receiver_zone.hdmi_output,
                ATTR_AUDIO_INFORMATION: self._receiver_zone.audio_information,
                ATTR_VIDEO_INFORMATION: self._receiver_zone.video_information,
            }
            if self._receiver_zone.powerstate == MediaPlayerState.ON
            else {}
        )

    async def async_select_source(self, source: str) -> None:
        """Change receiver zone to the designated source (by name)."""
        if source in self._source_list:
            mapped_source = self._reverse_source_mapping[source]
        self._receiver_zone.set_source(mapped_source)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Change receiver zone to the designated sound mode (by name)."""
        self._receiver_zone.set_sound_mode(sound_mode)

    async def async_turn_off(self) -> None:
        """Turn receiver zone power off."""
        self._receiver_zone.set_power_state(False)

    async def async_turn_on(self) -> None:
        """Turn receiver zone power on."""
        self._receiver_zone.set_power_state(True)

    async def async_volume_up(self) -> None:
        """Increment volume by 1 step."""
        if self._receiver_zone.volume < self._max_volume:
            self._receiver_zone.increase_volume()

    async def async_volume_down(self) -> None:
        """Decrement volume by 1 step."""
        self._receiver_zone.decrease_volume()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the receiver zone volume level (0 to 1)."""
        self._receiver_zone.set_volume(int(volume * self._max_volume))

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute/Unmute the receiver zone."""
        self._receiver_zone.set_mute(mute)

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: int
    ) -> None:
        """Play radio station by preset number."""
        self._receiver_zone.play_media(media_type, media_id)

    async def async_select_output(self, hdmi_output: str) -> None:
        """Set HDMI output."""
        self._receiver_zone.set_hdmi_output(hdmi_output)

    def _parse_unmapped_source(self, unmapped_source: tuple) -> str:
        """Parse the unmapped source from the receiver to a source from our own source mapping."""
        for value in unmapped_source:
            if value in self._source_mapping:
                return self._source_mapping[value]

        return "_".join(unmapped_source)
