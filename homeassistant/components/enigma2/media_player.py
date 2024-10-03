"""Support for Enigma2 media players."""

from __future__ import annotations

import contextlib
from logging import getLogger

from aiohttp.client_exceptions import ServerDisconnectedError
from openwebif.enums import PowerState, RemoteControlCodes, SetVolumeOption
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import Enigma2ConfigEntry
from .const import (
    CONF_DEEP_STANDBY,
    CONF_MAC_ADDRESS,
    CONF_SOURCE_BOUQUET,
    CONF_USE_CHANNEL_ICON,
    DEFAULT_DEEP_STANDBY,
    DEFAULT_MAC_ADDRESS,
    DEFAULT_NAME,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_SOURCE_BOUQUET,
    DEFAULT_SSL,
    DEFAULT_USE_CHANNEL_ICON,
    DEFAULT_USERNAME,
    DOMAIN,
)
from .coordinator import Enigma2UpdateCoordinator

ATTR_MEDIA_CURRENTLY_RECORDING = "media_currently_recording"
ATTR_MEDIA_DESCRIPTION = "media_description"
ATTR_MEDIA_END_TIME = "media_end_time"
ATTR_MEDIA_START_TIME = "media_start_time"

_LOGGER = getLogger(__name__)

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(
            CONF_USE_CHANNEL_ICON, default=DEFAULT_USE_CHANNEL_ICON
        ): cv.boolean,
        vol.Optional(CONF_DEEP_STANDBY, default=DEFAULT_DEEP_STANDBY): cv.boolean,
        vol.Optional(CONF_MAC_ADDRESS, default=DEFAULT_MAC_ADDRESS): cv.string,
        vol.Optional(CONF_SOURCE_BOUQUET, default=DEFAULT_SOURCE_BOUQUET): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up of an enigma2 media player."""

    entry_data = {
        CONF_HOST: config[CONF_HOST],
        CONF_PORT: config[CONF_PORT],
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
        CONF_SSL: config[CONF_SSL],
        CONF_USE_CHANNEL_ICON: config[CONF_USE_CHANNEL_ICON],
        CONF_DEEP_STANDBY: config[CONF_DEEP_STANDBY],
        CONF_SOURCE_BOUQUET: config[CONF_SOURCE_BOUQUET],
    }

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_data
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Enigma2ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Enigma2 media player platform."""
    async_add_entities([Enigma2Device(entry.runtime_data)])


class Enigma2Device(CoordinatorEntity[Enigma2UpdateCoordinator], MediaPlayerEntity):
    """Representation of an Enigma2 box."""

    _attr_has_entity_name = True
    _attr_name = None

    _attr_media_content_type = MediaType.TVSHOW
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, coordinator: Enigma2UpdateCoordinator) -> None:
        """Initialize the Enigma2 device."""

        super().__init__(coordinator)

        self._attr_unique_id = (
            coordinator.device.mac_address or coordinator.config_entry.entry_id
        )

        self._attr_device_info = coordinator.device_info

    async def async_turn_off(self) -> None:
        """Turn off media player."""
        if self.coordinator.device.turn_off_to_deep:
            with contextlib.suppress(ServerDisconnectedError):
                await self.coordinator.device.set_powerstate(PowerState.DEEP_STANDBY)
            self._attr_available = False
        else:
            await self.coordinator.device.set_powerstate(PowerState.STANDBY)
            await self.coordinator.async_refresh()

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self.coordinator.device.turn_on()
        await self.coordinator.async_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.coordinator.device.set_volume(int(volume * 100))
        await self.coordinator.async_refresh()

    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        await self.coordinator.device.set_volume(SetVolumeOption.UP)
        await self.coordinator.async_refresh()

    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self.coordinator.device.set_volume(SetVolumeOption.DOWN)
        await self.coordinator.async_refresh()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.coordinator.device.send_remote_control_action(
            RemoteControlCodes.STOP
        )
        await self.coordinator.async_refresh()

    async def async_media_play(self) -> None:
        """Play media."""
        await self.coordinator.device.send_remote_control_action(
            RemoteControlCodes.PLAY
        )
        await self.coordinator.async_refresh()

    async def async_media_pause(self) -> None:
        """Pause the media player."""
        await self.coordinator.device.send_remote_control_action(
            RemoteControlCodes.PAUSE
        )
        await self.coordinator.async_refresh()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.coordinator.device.send_remote_control_action(
            RemoteControlCodes.CHANNEL_UP
        )
        await self.coordinator.async_refresh()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.coordinator.device.send_remote_control_action(
            RemoteControlCodes.CHANNEL_DOWN
        )
        await self.coordinator.async_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        if mute != self.coordinator.data.muted:
            await self.coordinator.device.toggle_mute()
            await self.coordinator.async_refresh()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self.coordinator.device.zap(self.coordinator.device.sources[source])
        await self.coordinator.async_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update state of the media_player."""

        if not self.coordinator.data.in_standby:
            self._attr_extra_state_attributes = {
                # TODO(2025.5): Remove media currently recording
                ATTR_MEDIA_CURRENTLY_RECORDING: self.coordinator.data.is_recording,
                ATTR_MEDIA_DESCRIPTION: self.coordinator.data.currservice.fulldescription,
                ATTR_MEDIA_START_TIME: self.coordinator.data.currservice.begin,
                ATTR_MEDIA_END_TIME: self.coordinator.data.currservice.end,
            }
        else:
            self._attr_extra_state_attributes = {}

        self._attr_media_title = self.coordinator.data.currservice.station
        self._attr_media_series_title = self.coordinator.data.currservice.name
        self._attr_media_channel = self.coordinator.data.currservice.station
        self._attr_is_volume_muted = self.coordinator.data.muted
        self._attr_media_content_id = self.coordinator.data.currservice.serviceref
        self._attr_media_image_url = self.coordinator.device.picon_url
        self._attr_source = self.coordinator.data.currservice.station
        self._attr_source_list = self.coordinator.device.source_list

        if self.coordinator.data.in_standby:
            self._attr_state = MediaPlayerState.OFF
        else:
            self._attr_state = MediaPlayerState.ON

        if (volume_level := self.coordinator.data.volume) is not None:
            self._attr_volume_level = volume_level / 100
        else:
            self._attr_volume_level = None

        self.async_write_ha_state()
