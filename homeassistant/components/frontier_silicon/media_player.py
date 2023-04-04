"""Support for Frontier Silicon Devices (Medion, Hama, Auna,...)."""
from __future__ import annotations

import logging
from typing import Any

from afsapi import (
    AFSAPI,
    ConnectionError as FSConnectionError,
    NotImplementedException as FSNotImplementedException,
    PlayState,
)
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    BrowseError,
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .browse_media import browse_node, browse_top_level
from .const import CONF_PIN, DEFAULT_PIN, DEFAULT_PORT, DOMAIN, MEDIA_CONTENT_ID_PRESET

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PIN): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Frontier Silicon platform.

    YAML is deprecated, and imported automatically.
    """

    ir.async_create_issue(
        hass,
        DOMAIN,
        "remove_yaml",
        breaks_in_ha_version="2023.6.0",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="removed_yaml",
    )

    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_NAME: config.get(CONF_NAME),
            CONF_HOST: config.get(CONF_HOST),
            CONF_PORT: config.get(CONF_PORT, DEFAULT_PORT),
            CONF_PIN: config.get(CONF_PASSWORD, DEFAULT_PIN),
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Frontier Silicon entity."""

    afsapi: AFSAPI = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([AFSAPIDevice(config_entry.title, afsapi)], True)


class AFSAPIDevice(MediaPlayerEntity):
    """Representation of a Frontier Silicon device on the network."""

    _attr_media_content_type: str = MediaType.CHANNEL

    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )

    def __init__(self, name: str | None, afsapi: AFSAPI) -> None:
        """Initialize the Frontier Silicon API device."""
        self.fs_device = afsapi

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, afsapi.webfsapi_endpoint)},
            name=name,
        )
        self._attr_name = name

        self._max_volume: int | None = None

        self.__modes_by_label: dict[str, str] | None = None
        self.__sound_modes_by_label: dict[str, str] | None = None

        self._supports_sound_mode: bool = True

    async def async_update(self) -> None:
        """Get the latest date and update device state."""
        afsapi = self.fs_device
        try:
            if await afsapi.get_power():
                status = await afsapi.get_play_status()
                self._attr_state = {
                    PlayState.PLAYING: MediaPlayerState.PLAYING,
                    PlayState.PAUSED: MediaPlayerState.PAUSED,
                    PlayState.STOPPED: MediaPlayerState.IDLE,
                    PlayState.LOADING: MediaPlayerState.BUFFERING,
                    None: MediaPlayerState.IDLE,
                }.get(status)
            else:
                self._attr_state = MediaPlayerState.OFF
        except FSConnectionError:
            if self._attr_available:
                _LOGGER.warning(
                    "Could not connect to %s. Did it go offline?",
                    self.name or afsapi.webfsapi_endpoint,
                )
                self._attr_available = False
                return

        if not self._attr_available:
            _LOGGER.info(
                "Reconnected to %s",
                self.name or afsapi.webfsapi_endpoint,
            )

            self._attr_available = True
        if not self._attr_name:
            self._attr_name = await afsapi.get_friendly_name()

        if not self._attr_source_list:
            self.__modes_by_label = {
                mode.label: mode.key for mode in await afsapi.get_modes()
            }
            self._attr_source_list = list(self.__modes_by_label)

        if not self._attr_sound_mode_list and self._supports_sound_mode:
            try:
                equalisers = await afsapi.get_equalisers()
            except FSNotImplementedException:
                self._supports_sound_mode = False
                # Remove SELECT_SOUND_MODE from the advertised supported features
                self._attr_supported_features ^= (
                    MediaPlayerEntityFeature.SELECT_SOUND_MODE
                )
            else:
                self.__sound_modes_by_label = {
                    sound_mode.label: sound_mode.key for sound_mode in equalisers
                }
                self._attr_sound_mode_list = list(self.__sound_modes_by_label)

        # The API seems to include 'zero' in the number of steps (e.g. if the range is
        # 0-40 then get_volume_steps returns 41) subtract one to get the max volume.
        # If call to get_volume fails set to 0 and try again next time.
        if not self._max_volume:
            self._max_volume = int(await afsapi.get_volume_steps() or 1) - 1

        if self._attr_state != MediaPlayerState.OFF:
            info_name = await afsapi.get_play_name()
            info_text = await afsapi.get_play_text()

            self._attr_media_title = " - ".join(filter(None, [info_name, info_text]))
            self._attr_media_artist = await afsapi.get_play_artist()
            self._attr_media_album_name = await afsapi.get_play_album()

            radio_mode = await afsapi.get_mode()
            self._attr_source = radio_mode.label if radio_mode is not None else None

            self._attr_is_volume_muted = await afsapi.get_mute()
            self._attr_media_image_url = await afsapi.get_play_graphic()

            if self._supports_sound_mode:
                try:
                    eq_preset = await afsapi.get_eq_preset()
                except FSNotImplementedException:
                    self._supports_sound_mode = False
                    # Remove SELECT_SOUND_MODE from the advertised supported features
                    self._attr_supported_features ^= (
                        MediaPlayerEntityFeature.SELECT_SOUND_MODE
                    )
                else:
                    self._attr_sound_mode = (
                        eq_preset.label if eq_preset is not None else None
                    )

            volume = await self.fs_device.get_volume()

            # Prevent division by zero if max_volume not known yet
            self._attr_volume_level = float(volume or 0) / (self._max_volume or 1)
        else:
            self._attr_media_title = None
            self._attr_media_artist = None
            self._attr_media_album_name = None

            self._attr_source = None

            self._attr_is_volume_muted = None
            self._attr_media_image_url = None
            self._attr_sound_mode = None

            self._attr_volume_level = None

    # Management actions
    # power control
    async def async_turn_on(self) -> None:
        """Turn on the device."""
        await self.fs_device.set_power(True)

    async def async_turn_off(self) -> None:
        """Turn off the device."""
        await self.fs_device.set_power(False)

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.fs_device.play()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.fs_device.pause()

    async def async_media_play_pause(self) -> None:
        """Send play/pause command."""
        if self._attr_state == MediaPlayerState.PLAYING:
            await self.fs_device.pause()
        else:
            await self.fs_device.play()

    async def async_media_stop(self) -> None:
        """Send play/pause command."""
        await self.fs_device.pause()

    async def async_media_previous_track(self) -> None:
        """Send previous track command (results in rewind)."""
        await self.fs_device.rewind()

    async def async_media_next_track(self) -> None:
        """Send next track command (results in fast-forward)."""
        await self.fs_device.forward()

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self.fs_device.set_mute(mute)

    # volume
    async def async_volume_up(self) -> None:
        """Send volume up command."""
        volume = await self.fs_device.get_volume()
        volume = int(volume or 0) + 1
        await self.fs_device.set_volume(min(volume, self._max_volume))

    async def async_volume_down(self) -> None:
        """Send volume down command."""
        volume = await self.fs_device.get_volume()
        volume = int(volume or 0) - 1
        await self.fs_device.set_volume(max(volume, 0))

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume command."""
        if self._max_volume:  # Can't do anything sensible if not set
            volume = int(volume * self._max_volume)
            await self.fs_device.set_volume(volume)

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self.fs_device.set_power(True)
        if (
            self.__modes_by_label
            and (mode := self.__modes_by_label.get(source)) is not None
        ):
            await self.fs_device.set_mode(mode)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select EQ Preset."""
        if (
            self.__sound_modes_by_label
            and (mode := self.__sound_modes_by_label.get(sound_mode)) is not None
        ):
            await self.fs_device.set_eq_preset(mode)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse media library and preset stations."""
        if not media_content_id:
            return await browse_top_level(self._attr_source, self.fs_device)

        return await browse_node(self.fs_device, media_content_type, media_content_id)

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play selected media or channel."""
        if media_type != MediaType.CHANNEL:
            _LOGGER.error(
                "Got %s, but frontier_silicon only supports playing channels",
                media_type,
            )
            return

        player_mode, media_type, *keys = media_id.split("/")

        await self.async_select_source(player_mode)  # this also powers on the device

        if media_type == MEDIA_CONTENT_ID_PRESET:
            if len(keys) != 1:
                raise BrowseError("Presets can only have 1 level")

            # Keys of presets are 0-based, while the list shown on the device starts from 1
            preset = int(keys[0]) - 1

            result = await self.fs_device.select_preset(preset)
        else:
            result = await self.fs_device.nav_select_item_via_path(keys)

        await self.async_update()
        self._attr_media_content_id = media_id
        return result
