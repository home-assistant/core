"""Support for Enigma2 media players."""
from __future__ import annotations

from aiohttp.client_exceptions import ClientConnectorError
from openwebif.api import OpenWebIfDevice
from openwebif.enums import RemoteControlCodes, SetVolumeOption
import voluptuous as vol
from yarl import URL

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

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
)

ATTR_MEDIA_CURRENTLY_RECORDING = "media_currently_recording"
ATTR_MEDIA_DESCRIPTION = "media_description"
ATTR_MEDIA_END_TIME = "media_end_time"
ATTR_MEDIA_START_TIME = "media_start_time"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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
    if discovery_info:
        # Discovery gives us the streaming service port (8001)
        # which is not useful as OpenWebif never runs on that port.
        # So use the default port instead.
        config[CONF_PORT] = DEFAULT_PORT
        config[CONF_NAME] = discovery_info["hostname"]
        config[CONF_HOST] = discovery_info["host"]
        config[CONF_USERNAME] = DEFAULT_USERNAME
        config[CONF_PASSWORD] = DEFAULT_PASSWORD
        config[CONF_SSL] = DEFAULT_SSL
        config[CONF_USE_CHANNEL_ICON] = DEFAULT_USE_CHANNEL_ICON
        config[CONF_MAC_ADDRESS] = DEFAULT_MAC_ADDRESS
        config[CONF_DEEP_STANDBY] = DEFAULT_DEEP_STANDBY
        config[CONF_SOURCE_BOUQUET] = DEFAULT_SOURCE_BOUQUET

    base_url = URL.build(
        scheme="https" if config[CONF_SSL] else "http",
        host=config[CONF_HOST],
        port=config.get(CONF_PORT),
        user=config.get(CONF_USERNAME),
        password=config.get(CONF_PASSWORD),
    )

    session = async_create_clientsession(hass, verify_ssl=False, base_url=base_url)

    device = OpenWebIfDevice(
        host=session,
        turn_off_to_deep=config.get(CONF_DEEP_STANDBY),
        source_bouquet=config.get(CONF_SOURCE_BOUQUET),
    )

    try:
        about = await device.get_about()
    except ClientConnectorError as err:
        raise PlatformNotReady from err

    async_add_entities([Enigma2Device(config[CONF_NAME], device, about)])


class Enigma2Device(MediaPlayerEntity):
    """Representation of an Enigma2 box."""

    _attr_has_entity_name = True

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

    def __init__(self, name: str, device: OpenWebIfDevice, about: dict) -> None:
        """Initialize the Enigma2 device."""
        self._device: OpenWebIfDevice = device
        self._device.mac_address = about["info"]["ifaces"][0]["mac"]

        self._attr_name = name
        self._attr_unique_id = device.mac_address

    async def async_turn_off(self) -> None:
        """Turn off media player."""
        await self._device.turn_off()

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._device.turn_on()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._device.set_volume(int(volume * 100))

    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        await self._device.set_volume(SetVolumeOption.UP)

    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self._device.set_volume(SetVolumeOption.DOWN)

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._device.send_remote_control_action(RemoteControlCodes.STOP)

    async def async_media_play(self) -> None:
        """Play media."""
        await self._device.send_remote_control_action(RemoteControlCodes.PLAY)

    async def async_media_pause(self) -> None:
        """Pause the media player."""
        await self._device.send_remote_control_action(RemoteControlCodes.PAUSE)

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._device.send_remote_control_action(RemoteControlCodes.CHANNEL_UP)

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._device.send_remote_control_action(RemoteControlCodes.CHANNEL_DOWN)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        await self._device.toggle_mute()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self._device.zap(self._device.sources[source])

    async def async_update(self) -> None:
        """Update state of the media_player."""
        await self._device.update()
        self._attr_available = not self._device.is_offline

        if not self._device.status.in_standby:
            self._attr_extra_state_attributes = {
                ATTR_MEDIA_CURRENTLY_RECORDING: self._device.status.is_recording,
                ATTR_MEDIA_DESCRIPTION: self._device.status.currservice.fulldescription,
                ATTR_MEDIA_START_TIME: self._device.status.currservice.begin,
                ATTR_MEDIA_END_TIME: self._device.status.currservice.end,
            }
        else:
            self._attr_extra_state_attributes = {}

        self._attr_media_title = self._device.status.currservice.station
        self._attr_media_series_title = self._device.status.currservice.name
        self._attr_media_channel = self._device.status.currservice.station
        self._attr_is_volume_muted = self._device.status.muted
        self._attr_media_content_id = self._device.status.currservice.serviceref
        self._attr_media_image_url = self._device.picon_url
        self._attr_source = self._device.status.currservice.station
        self._attr_source_list = self._device.source_list

        if self._device.status.in_standby:
            self._attr_state = MediaPlayerState.OFF
        else:
            self._attr_state = MediaPlayerState.ON

        if (volume_level := self._device.status.volume) is not None:
            self._attr_volume_level = volume_level / 100
        else:
            self._attr_volume_level = None
