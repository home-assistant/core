"""Support for Frontier Silicon Devices (Medion, Hama, Auna,...)."""
from __future__ import annotations

import logging

from afsapi import (
    AFSAPI,
    ConnectionError as FSConnectionError,
    NotImplementedException as FSNotImplementedException,
    PlayState,
)
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.const import MEDIA_TYPE_MUSIC
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_IDLE,
    STATE_OFF,
    STATE_OPENING,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_PIN, DEFAULT_PORT, DOMAIN

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
    """Set up the Frontier Silicon platform."""
    if discovery_info is not None:
        webfsapi_url = await AFSAPI.get_webfsapi_endpoint(
            discovery_info["ssdp_description"]
        )
        afsapi = AFSAPI(webfsapi_url, DEFAULT_PIN)

        name = await afsapi.get_friendly_name()
        async_add_entities(
            [AFSAPIDevice(name, afsapi)],
            True,
        )
        return

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    password = config.get(CONF_PASSWORD)
    name = config.get(CONF_NAME)

    try:
        webfsapi_url = await AFSAPI.get_webfsapi_endpoint(
            f"http://{host}:{port}/device"
        )
    except FSConnectionError:
        _LOGGER.error(
            "Could not add the FSAPI device at %s:%s -> %s", host, port, password
        )
        return
    afsapi = AFSAPI(webfsapi_url, password)
    async_add_entities([AFSAPIDevice(name, afsapi)], True)


class AFSAPIDevice(MediaPlayerEntity):
    """Representation of a Frontier Silicon device on the network."""

    _attr_media_content_type: str = MEDIA_TYPE_MUSIC

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
                    PlayState.PLAYING: STATE_PLAYING,
                    PlayState.PAUSED: STATE_PAUSED,
                    PlayState.STOPPED: STATE_IDLE,
                    PlayState.LOADING: STATE_OPENING,
                    None: STATE_IDLE,
                }.get(status)
            else:
                self._attr_state = STATE_OFF
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

        if self._attr_state != STATE_OFF:
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
        if self._attr_state == STATE_PLAYING:
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
