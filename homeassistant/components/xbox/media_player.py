"""Xbox Media Player Support."""
import logging
from typing import Optional

from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.api.provider.catalog.models import (
    AlternateIdType,
    CatalogResponse,
    Image,
    Product,
)
from xbox.webapi.api.provider.smartglass.models import (
    PlaybackState,
    PowerState,
    SmartglassConsole,
    SmartglassConsoleList,
    SmartglassConsoleStatus,
    VolumeDirection,
)

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNKNOWN,
)

from .const import DOMAIN, HOME_BIG_ID

_LOGGER = logging.getLogger(__name__)

SUPPORT_XBOX = (
    SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PLAY
    | SUPPORT_PAUSE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
)

XBOX_STATE_MAP = {
    PlaybackState.Playing: STATE_PLAYING,
    PlaybackState.Paused: STATE_PAUSED,
    PowerState.On: STATE_ON,
    PowerState.SystemUpdate: STATE_OFF,
    PowerState.ConnectedStandby: STATE_OFF,
    PowerState.Off: STATE_OFF,
    PowerState.Unknown: STATE_UNKNOWN,
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Xbox media_player from a config entry."""
    client: XboxLiveClient = hass.data[DOMAIN][entry.entry_id]
    consoles: SmartglassConsoleList = await client.smartglass.get_console_list()
    async_add_entities(
        [XboxMediaPlayer(client, console) for console in consoles.result], True
    )


class XboxMediaPlayer(MediaPlayerEntity):
    """Representation of an Xbox device."""

    def __init__(self, client: XboxLiveClient, console: SmartglassConsole) -> None:
        """Initialize the Plex device."""
        self.client: XboxLiveClient = client
        self._console: SmartglassConsole = console

        self._console_status: SmartglassConsoleStatus = None
        self._app_details: Optional[Product] = None

    @property
    def name(self):
        """Return the device name."""
        return self._console.name

    @property
    def unique_id(self):
        """Console device ID."""
        return self._console.id

    @property
    def state(self):
        """State of the player."""
        if self._console_status.playback_state in XBOX_STATE_MAP:
            return XBOX_STATE_MAP[self._console_status.playback_state]
        return XBOX_STATE_MAP[self._console_status.power_state]

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        active_support = SUPPORT_XBOX
        if self.state not in [STATE_PLAYING, STATE_PAUSED]:
            active_support &= ~SUPPORT_NEXT_TRACK & ~SUPPORT_PREVIOUS_TRACK
        if not self._console_status.is_tv_configured:
            active_support &= ~SUPPORT_VOLUME_MUTE & ~SUPPORT_VOLUME_STEP
        return active_support

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self._app_details:
            image: Image = next(
                image
                for image in self._app_details.localized_properties.images
                if image.width >= 300 and image.image_purpose in ["Logo", "BoxArt"]
            )
            url = image.uri
            if url[0] == "/":
                url = f"http:{url}"
            return url
        return None

    @property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        return True

    async def async_update(self) -> None:
        """Update Xbox state."""
        status: SmartglassConsoleStatus = (
            await self.client.smartglass.get_console_status(self._console.id)
        )

        catalog_result: CatalogResponse = None
        if not status.focus_app_aumid:
            catalog_result = await self.client.catalog.get_products([HOME_BIG_ID])
        elif (
            not self._console_status
            or status.focus_app_aumid != self._console_status.focus_app_aumid
        ):
            catalog_result = await self.client.catalog.get_product_from_alternate_id(
                status.focus_app_aumid.split("!")[0],
                AlternateIdType.PACKAGE_FAMILY_NAME,
            )

        if catalog_result and len(catalog_result.products):
            self._app_details = catalog_result.products[0]
        else:
            self._app_details = None

        self._console_status = status

    async def async_turn_on(self):
        """Turn the media player on."""
        await self.client.smartglass.wake_up(self._console.id)

    async def async_turn_off(self):
        """Turn the media player off."""
        await self.client.smartglass.turn_off(self._console.id)

    async def async_mute_volume(self, mute):
        """Mute the volume."""
        await self.client.smartglass.mute(self._console.id)

    async def async_volume_up(self):
        """Turn volume up for media player."""
        await self.client.smartglass.volume(self._console.id, VolumeDirection.Up)

    async def async_volume_down(self):
        """Turn volume down for media player."""
        await self.client.smartglass.volume(self._console.id, VolumeDirection.Down)

    async def async_media_play(self):
        """Send play command."""
        await self.client.smartglass.play(self._console.id)

    async def async_media_pause(self):
        """Send pause command."""
        await self.client.smartglass.pause(self._console.id)

    async def async_media_previous_track(self):
        """Send previous track command."""
        await self.client.smartglass.previous(self._console.id)

    async def async_media_next_track(self):
        """Send next track command."""
        await self.client.smartglass.next(self._console.id)
