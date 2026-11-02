"""Support for Ubiquiti's UniFi Protect NVR."""

import logging
from typing import TYPE_CHECKING, Any, cast, override

from uiprotect.data import (
    Camera,
    ModelType,
    ProtectAdoptableDeviceModel,
    PublicDeviceModel,
)
from uiprotect.data.public_devices import PublicCamera
from uiprotect.exceptions import StreamError

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import ProtectDeviceEntity
from .utils import async_ufp_instance_command

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0

_SPEAKER_DESCRIPTION = MediaPlayerEntityDescription(
    key="speaker",
    translation_key="speaker",
    device_class=MediaPlayerDeviceClass.SPEAKER,
)

_PLAYBACK_FEATURES = (
    MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.BROWSE_MEDIA
)
# Speaker volume is not in the public API.
_VOLUME_FEATURES = (
    MediaPlayerEntityFeature.VOLUME_SET | MediaPlayerEntityFeature.VOLUME_STEP
)


def _has_speaker(public: PublicDeviceModel) -> bool:
    return cast(PublicCamera, public).has_speaker


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Discover cameras with speakers on a UniFi Protect NVR."""
    data = entry.runtime_data

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        # AiPort inherits from Camera but should not create camera-specific entities
        if (
            device.model is ModelType.CAMERA
            and isinstance(device, Camera)
            and (device.has_speaker or device.has_removable_speaker)
        ):
            public = data.async_get_public_device(device)
            async_add_entities(
                [
                    ProtectMediaPlayer(
                        data,
                        public if isinstance(public, PublicCamera) else None,
                        device,
                    )
                ]
            )

    @callback
    def _add_new_public_device(device: PublicDeviceModel) -> None:
        # Only public-only mode offers cameras here; hybrid adopts them above.
        # The signal fires once per mac, so a speaker attached later only gets
        # an entity after a reload.
        if isinstance(device, PublicCamera) and device.has_speaker:
            async_add_entities([ProtectMediaPlayer(data, device, None)])

    data.async_subscribe_adopt(_add_new_device)
    entry.async_on_unload(
        async_dispatcher_connect(hass, data.public_add_signal, _add_new_public_device)
    )

    entities: list[ProtectMediaPlayer] = []
    for public, private in data.get_public_cameras():
        if private is None:
            # Hybrid defers a camera without private fill to the adopt dispatch.
            if data.api.is_public_only and public is not None and public.has_speaker:
                entities.append(ProtectMediaPlayer(data, public, None))
            continue
        # Created even without a public mirror; unavailable until one arrives.
        if private.has_speaker or private.has_removable_speaker:
            entities.append(ProtectMediaPlayer(data, public, private))
    async_add_entities(entities)


class ProtectMediaPlayer(ProtectDeviceEntity, MediaPlayerEntity):
    """A Ubiquiti UniFi Protect Speaker."""

    device: Camera | PublicCamera
    entity_description: MediaPlayerEntityDescription
    _attr_supported_features = _PLAYBACK_FEATURES | _VOLUME_FEATURES
    _attr_media_content_type = MediaType.MUSIC
    _state_attrs = ("_attr_available", "_attr_state", "_attr_volume_level")
    # Playback goes through the public camera; the base class primes the object
    # and subscribes to the public devices websocket on this flag.
    _ufp_uses_public = True

    def __init__(
        self,
        data: ProtectData,
        public: PublicCamera | None,
        private: Camera | None,
    ) -> None:
        """Initialize the speaker."""
        self._ufp_public_obj = public
        # unique_id and device info derive from the base device, so hybrid must
        # keep the private one to leave existing entities unchanged.
        device = private or public
        if TYPE_CHECKING:
            # The platform only builds a speaker when at least one side exists.
            assert device is not None
        super().__init__(data, device, _SPEAKER_DESCRIPTION)
        self._async_get_ufp_public_enabled = _has_speaker
        if private is None:
            self._attr_supported_features = _PLAYBACK_FEATURES

    @callback
    @override
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        if isinstance(camera := self.device, Camera):
            speaker_settings = camera.speaker_settings
            volume = (
                speaker_settings.speaker_volume
                if speaker_settings.speaker_volume is not None
                else speaker_settings.volume
            )
            self._attr_volume_level = float(volume / 100)

        public = cast(PublicCamera | None, self._ufp_public_obj)
        stream = public.talkback_stream if public is not None else None
        if stream is not None and stream.is_running:
            self._attr_state = MediaPlayerState.PLAYING
        else:
            self._attr_state = MediaPlayerState.IDLE

    def _public_camera(self) -> PublicCamera:
        """Return the public camera, or raise if it vanished mid-command."""
        return cast(PublicCamera, self._ufp_set_target())

    @async_ufp_instance_command
    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        if TYPE_CHECKING:
            # Only offered with a private camera.
            assert isinstance(self.device, Camera)
        await self.device.set_speaker_volume(int(volume * 100))

    @async_ufp_instance_command
    @override
    async def async_media_stop(self) -> None:
        """Send stop command."""
        camera = self._public_camera()
        if (stream := camera.talkback_stream) is not None and stream.is_running:
            _LOGGER.debug("Stopping playback for %s Speaker", camera.display_name)
            await camera.stop_audio()
            self._async_updated_event(self.device)

    @async_ufp_instance_command
    @override
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        if media_source.is_media_source_id(media_id):
            media_type = MediaType.MUSIC
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = async_process_play_media_url(self.hass, play_item.url)

        if media_type != MediaType.MUSIC:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="only_music_supported",
            )

        camera = self._public_camera()
        _LOGGER.debug("Playing Media %s for %s Speaker", media_id, camera.display_name)
        await self.async_media_stop()
        try:
            await camera.play_audio(media_id, blocking=False)
            self._async_updated_event(self.device)
            await camera.wait_until_audio_completes()
        except StreamError as err:
            _LOGGER.debug("Error playing audio: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="stream_error",
            ) from err
        finally:
            self._async_updated_event(self.device)

    @override
    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )
