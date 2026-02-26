"""Xbox Media Player Support."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from http import HTTPStatus
import logging
from typing import Any, Concatenate

from httpx import HTTPStatusError, RequestError, TimeoutException
from pythonxbox.api.provider.catalog.models import Image
from pythonxbox.api.provider.smartglass.models import (
    PlaybackState,
    PowerState,
    VolumeDirection,
)

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .browse_media import build_item_response
from .const import DOMAIN
from .coordinator import XboxConfigEntry
from .entity import XboxConsoleBaseEntity, to_https

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

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
    hass: HomeAssistant,
    entry: XboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Xbox media_player from a config entry."""
    devices_added: set[str] = set()

    status = entry.runtime_data.status
    consoles = entry.runtime_data.consoles

    @callback
    def add_entities() -> None:
        nonlocal devices_added

        new_devices = set(consoles.data) - devices_added

        if new_devices:
            async_add_entities(
                [
                    XboxMediaPlayer(consoles.data[console_id], status)
                    for console_id in new_devices
                ]
            )
            devices_added |= new_devices
        devices_added &= set(consoles.data)

    entry.async_on_unload(consoles.async_add_listener(add_entities))
    add_entities()


def exception_handler[**_P, _R](
    func: Callable[Concatenate[XboxMediaPlayer, _P], Awaitable[_R]],
) -> Callable[Concatenate[XboxMediaPlayer, _P], Coroutine[Any, Any, _R]]:
    """Catch Xbox errors."""

    @wraps(func)
    async def wrapper(
        self: XboxMediaPlayer,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _R:
        """Catch Xbox errors and raise HomeAssistantError."""
        try:
            return await func(self, *args, **kwargs)
        except TimeoutException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout_exception",
            ) from e
        except (RequestError, HTTPStatusError) as e:
            _LOGGER.debug("Xbox exception:", exc_info=True)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="request_exception",
            ) from e

    return wrapper


class XboxMediaPlayer(XboxConsoleBaseEntity, MediaPlayerEntity):
    """Representation of an Xbox Media Player."""

    _attr_media_image_remotely_accessible = True
    _attr_translation_key = "xbox"

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
    def media_content_type(self) -> MediaType:
        """Media content type."""

        return (
            MediaType.GAME
            if self.data.app_details and self.data.app_details.product_family == "Games"
            else MediaType.APP
        )

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        return self.data.app_details.product_id if self.data.app_details else None

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return (
            (
                app_details.localized_properties[0].product_title
                or app_details.localized_properties[0].short_title
            )
            if (app_details := self.data.app_details)
            else None
        )

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""

        return (
            to_https(image.uri)
            if (app_details := self.data.app_details)
            and (image := _find_media_image(app_details.localized_properties[0].images))
            else None
        )

    @exception_handler
    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        try:
            await self.client.smartglass.wake_up(self._console.id)
        except HTTPStatusError as e:
            if e.response.status_code == HTTPStatus.NOT_FOUND:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="turn_on_failed",
                ) from e
            raise

    @exception_handler
    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self.client.smartglass.turn_off(self._console.id)

    @exception_handler
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""

        if mute:
            await self.client.smartglass.mute(self._console.id)
        else:
            await self.client.smartglass.unmute(self._console.id)

        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    @exception_handler
    async def async_volume_up(self) -> None:
        """Turn volume up for media player."""

        await self.client.smartglass.volume(self._console.id, VolumeDirection.Up)

    @exception_handler
    async def async_volume_down(self) -> None:
        """Turn volume down for media player."""

        await self.client.smartglass.volume(self._console.id, VolumeDirection.Down)

    @exception_handler
    async def async_media_play(self) -> None:
        """Send play command."""

        await self.client.smartglass.play(self._console.id)

    @exception_handler
    async def async_media_pause(self) -> None:
        """Send pause command."""

        await self.client.smartglass.pause(self._console.id)

    @exception_handler
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""

        await self.client.smartglass.previous(self._console.id)

    @exception_handler
    async def async_media_next_track(self) -> None:
        """Send next track command."""

        await self.client.smartglass.next(self._console.id)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""

        return await build_item_response(
            self.client,
            self._console.id,
            media_content_type,
            media_content_id,
        )

    @exception_handler
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Launch an app on the Xbox."""

        if media_id == "Home":
            await self.client.smartglass.go_home(self._console.id)

        await self.client.smartglass.launch_app(self._console.id, media_id)


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
