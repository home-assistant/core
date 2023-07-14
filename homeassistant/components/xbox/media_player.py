"""Xbox Media Player Support."""
from __future__ import annotations

import re
from typing import Any

from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.api.provider.catalog.models import Image
from xbox.webapi.api.provider.smartglass.models import (
    PlaybackState,
    PowerState,
    SmartglassConsole,
    SmartglassConsoleList,
    VolumeDirection,
)

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ConsoleData, XboxUpdateCoordinator
from .browse_media import build_item_response
from .const import DOMAIN

SUPPORT_XBOX = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.PLAY_MEDIA
)

XBOX_STATE_MAP: dict[PlaybackState | PowerState, MediaPlayerState | None] = {
    PlaybackState.Playing: MediaPlayerState.PLAYING,
    PlaybackState.Paused: MediaPlayerState.PAUSED,
    PowerState.On: MediaPlayerState.ON,
    PowerState.SystemUpdate: MediaPlayerState.OFF,
    PowerState.ConnectedStandby: MediaPlayerState.OFF,
    PowerState.Off: MediaPlayerState.OFF,
    PowerState.Unknown: None,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Xbox media_player from a config entry."""
    client: XboxLiveClient = hass.data[DOMAIN][entry.entry_id]["client"]
    consoles: SmartglassConsoleList = hass.data[DOMAIN][entry.entry_id]["consoles"]
    coordinator: XboxUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    async_add_entities(
        [XboxMediaPlayer(client, console, coordinator) for console in consoles.result]
    )


class XboxMediaPlayer(CoordinatorEntity[XboxUpdateCoordinator], MediaPlayerEntity):
    """Representation of an Xbox Media Player."""

    def __init__(
        self,
        client: XboxLiveClient,
        console: SmartglassConsole,
        coordinator: XboxUpdateCoordinator,
    ) -> None:
        """Initialize the Xbox Media Player."""
        super().__init__(coordinator)
        self.client: XboxLiveClient = client
        self._console: SmartglassConsole = console

    @property
    def name(self):
        """Return the device name."""
        return self._console.name

    @property
    def unique_id(self):
        """Console device ID."""
        return self._console.id

    @property
    def data(self) -> ConsoleData:
        """Return coordinator data for this console."""
        return self.coordinator.data.consoles[self._console.id]

    @property
    def state(self) -> MediaPlayerState | None:
        """State of the player."""
        status = self.data.status
        if status.playback_state in XBOX_STATE_MAP:
            return XBOX_STATE_MAP[status.playback_state]
        return XBOX_STATE_MAP[status.power_state]

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        if self.state not in [MediaPlayerState.PLAYING, MediaPlayerState.PAUSED]:
            return (
                SUPPORT_XBOX
                & ~MediaPlayerEntityFeature.NEXT_TRACK
                & ~MediaPlayerEntityFeature.PREVIOUS_TRACK
            )
        return SUPPORT_XBOX

    @property
    def media_content_type(self):
        """Media content type."""
        app_details = self.data.app_details
        if app_details and app_details.product_family == "Games":
            return MediaType.GAME
        return MediaType.APP

    @property
    def media_title(self):
        """Title of current playing media."""
        if not (app_details := self.data.app_details):
            return None
        return (
            app_details.localized_properties[0].product_title
            or app_details.localized_properties[0].short_title
        )

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if not (app_details := self.data.app_details):
            return None
        image = _find_media_image(app_details.localized_properties[0].images)

        if not image:
            return None

        url = image.uri
        if url[0] == "/":
            url = f"http:{url}"
        return url

    @property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        return True

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self.client.smartglass.wake_up(self._console.id)

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self.client.smartglass.turn_off(self._console.id)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        if mute:
            await self.client.smartglass.mute(self._console.id)
        else:
            await self.client.smartglass.unmute(self._console.id)

    async def async_volume_up(self) -> None:
        """Turn volume up for media player."""
        await self.client.smartglass.volume(self._console.id, VolumeDirection.Up)

    async def async_volume_down(self) -> None:
        """Turn volume down for media player."""
        await self.client.smartglass.volume(self._console.id, VolumeDirection.Down)

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.client.smartglass.play(self._console.id)

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.client.smartglass.pause(self._console.id)

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.client.smartglass.previous(self._console.id)

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.client.smartglass.next(self._console.id)

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""
        return await build_item_response(
            self.client,
            self._console.id,
            self.data.status.is_tv_configured,
            media_content_type,
            media_content_id,
        )

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Launch an app on the Xbox."""
        if media_id == "Home":
            await self.client.smartglass.go_home(self._console.id)
        elif media_id == "TV":
            await self.client.smartglass.show_tv_guide(self._console.id)
        else:
            await self.client.smartglass.launch_app(self._console.id, media_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        # Turns "XboxOneX" into "Xbox One X" for display
        matches = re.finditer(
            ".+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)",
            self._console.console_type,
        )

        return DeviceInfo(
            identifiers={(DOMAIN, self._console.id)},
            manufacturer="Microsoft",
            model=" ".join([m.group(0) for m in matches]),
            name=self._console.name,
        )


def _find_media_image(images: list[Image]) -> Image | None:
    purpose_order = ["FeaturePromotionalSquareArt", "Tile", "Logo", "BoxArt"]
    for purpose in purpose_order:
        for image in images:
            if (
                image.image_purpose == purpose
                and image.width == image.height
                and image.width >= 300
            ):
                return image
    return None
