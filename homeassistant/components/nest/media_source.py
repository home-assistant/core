"""Nest Media Source implementation.

The Nest MediaSource implementation provides a directory tree of devices and
events and associated media (e.g. an image or clip). Camera device events
publish an event message, received by the subscriber library. Media for an
event, such as camera image or clip, may be fetched from the cloud during a
short time window after the event happens.

The actual management of associating events to devices, fetching media for
events, caching, and the overall lifetime of recent events are managed outside
of the Nest MediaSource.

Users may also record clips to local storage, unrelated to this MediaSource.

For additional background on Nest Camera events see:
https://developers.google.com/nest/device-access/api/camera#handle_camera_events
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import logging
import os
from typing import Any

from google_nest_sdm.camera_traits import CameraClipPreviewTrait, CameraEventImageTrait
from google_nest_sdm.device import Device
from google_nest_sdm.event import EventImageType, ImageEventBase
from google_nest_sdm.event_media import (
    ClipPreviewSession,
    EventMediaStore,
    ImageSession,
)
from google_nest_sdm.google_nest_subscriber import GoogleNestSubscriber
from google_nest_sdm.transcoder import Transcoder

from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .device_info import NestDeviceInfo, async_nest_devices_by_device_id
from .events import EVENT_NAME_MAP, MEDIA_SOURCE_EVENT_TITLE_MAP

_LOGGER = logging.getLogger(__name__)

MEDIA_SOURCE_TITLE = "Nest"
DEVICE_TITLE_FORMAT = "{device_name}: Recent Events"
CLIP_TITLE_FORMAT = "{event_name} @ {event_time}"
EVENT_MEDIA_API_URL_FORMAT = "/api/nest/event_media/{device_id}/{event_token}"
EVENT_THUMBNAIL_URL_FORMAT = "/api/nest/event_media/{device_id}/{event_token}/thumbnail"

STORAGE_KEY = "nest.event_media"
STORAGE_VERSION = 1
# Buffer writes every few minutes (plus guaranteed to be written at shutdown)
STORAGE_SAVE_DELAY_SECONDS = 120
# Path under config directory
MEDIA_PATH = f"{DOMAIN}/event_media"

# Size of small in-memory disk cache to avoid excessive disk reads
DISK_READ_LRU_MAX_SIZE = 32


async def async_get_media_event_store(
    hass: HomeAssistant, subscriber: GoogleNestSubscriber
) -> EventMediaStore:
    """Create the disk backed EventMediaStore."""
    media_path = hass.config.path(MEDIA_PATH)

    def mkdir() -> None:
        os.makedirs(media_path, exist_ok=True)

    await hass.async_add_executor_job(mkdir)
    store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY, private=True)
    return NestEventMediaStore(hass, subscriber, store, media_path)


async def async_get_transcoder(hass: HomeAssistant) -> Transcoder:
    """Get a nest clip transcoder."""
    media_path = hass.config.path(MEDIA_PATH)
    ffmpeg_manager = get_ffmpeg_manager(hass)
    return Transcoder(ffmpeg_manager.binary, media_path)


class NestEventMediaStore(EventMediaStore):
    """Storage hook to locally persist nest media for events.

    This interface is meant to provide two storage features:
    - media storage of events (jpgs, mp4s)
    - metadata about events (e.g. motion, person), filename of the media, etc.

    The default implementation in nest is in memory, and this allows the data
    to be backed by disk.

    The nest event media manager internal to the subscriber manages the lifetime
    of individual objects stored here (e.g. purging when going over storage
    limits). This store manages the addition/deletion once instructed.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        subscriber: GoogleNestSubscriber,
        store: Store[dict[str, Any]],
        media_path: str,
    ) -> None:
        """Initialize NestEventMediaStore."""
        self._hass = hass
        self._subscriber = subscriber
        self._store = store
        self._media_path = media_path
        self._data: dict[str, Any] | None = None
        self._devices: Mapping[str, str] | None = {}

    async def async_load(self) -> dict | None:
        """Load data."""
        if self._data is None:
            self._devices = await self._get_devices()
            if (data := await self._store.async_load()) is None:
                _LOGGER.debug("Loaded empty event store")
                self._data = {}
            else:
                _LOGGER.debug("Loaded event store with %d records", len(data))
                self._data = data
        return self._data

    async def async_save(self, data: dict) -> None:
        """Save data."""
        self._data = data

        def provide_data() -> dict:
            return data

        self._store.async_delay_save(provide_data, STORAGE_SAVE_DELAY_SECONDS)

    def get_media_key(self, device_id: str, event: ImageEventBase) -> str:
        """Return the filename to use for a new event."""
        if event.event_image_type != EventImageType.IMAGE:
            raise ValueError("No longer used for video clips")
        return self.get_image_media_key(device_id, event)

    def _map_device_id(self, device_id: str) -> str:
        return (
            self._devices.get(device_id, f"{device_id}-unknown_device")
            if self._devices
            else "unknown_device"
        )

    def get_image_media_key(self, device_id: str, event: ImageEventBase) -> str:
        """Return the filename for image media for an event."""
        device_id_str = self._map_device_id(device_id)
        time_str = str(int(event.timestamp.timestamp()))
        event_type_str = EVENT_NAME_MAP.get(event.event_type, "event")
        return f"{device_id_str}/{time_str}-{event_type_str}.jpg"

    def get_clip_preview_media_key(self, device_id: str, event: ImageEventBase) -> str:
        """Return the filename for clip preview media for an event session."""
        device_id_str = self._map_device_id(device_id)
        time_str = str(int(event.timestamp.timestamp()))
        event_type_str = EVENT_NAME_MAP.get(event.event_type, "event")
        return f"{device_id_str}/{time_str}-{event_type_str}.mp4"

    def get_clip_preview_thumbnail_media_key(
        self, device_id: str, event: ImageEventBase
    ) -> str:
        """Return the filename for clip preview thumbnail media for an event session."""
        device_id_str = self._map_device_id(device_id)
        time_str = str(int(event.timestamp.timestamp()))
        event_type_str = EVENT_NAME_MAP.get(event.event_type, "event")
        return f"{device_id_str}/{time_str}-{event_type_str}_thumb.gif"

    def get_media_filename(self, media_key: str) -> str:
        """Return the filename in storage for a media key."""
        return f"{self._media_path}/{media_key}"

    async def async_load_media(self, media_key: str) -> bytes | None:
        """Load media content."""
        filename = self.get_media_filename(media_key)

        def load_media(filename: str) -> bytes | None:
            if not os.path.exists(filename):
                return None
            _LOGGER.debug("Reading event media from disk store: %s", filename)
            with open(filename, "rb") as media:
                return media.read()

        try:
            return await self._hass.async_add_executor_job(load_media, filename)
        except OSError as err:
            _LOGGER.error("Unable to read media file: %s %s", filename, err)
            return None

    async def async_save_media(self, media_key: str, content: bytes) -> None:
        """Write media content."""
        filename = self.get_media_filename(media_key)

        def save_media(filename: str, content: bytes) -> None:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            if os.path.exists(filename):
                _LOGGER.debug(
                    "Event media already exists, not overwriting: %s", filename
                )
                return
            _LOGGER.debug("Saving event media to disk store: %s", filename)
            with open(filename, "wb") as media:
                media.write(content)

        try:
            await self._hass.async_add_executor_job(save_media, filename, content)
        except OSError as err:
            _LOGGER.error("Unable to write media file: %s %s", filename, err)

    async def async_remove_media(self, media_key: str) -> None:
        """Remove media content."""
        filename = self.get_media_filename(media_key)

        def remove_media(filename: str) -> None:
            if not os.path.exists(filename):
                return
            _LOGGER.debug("Removing event media from disk store: %s", filename)
            os.remove(filename)

        try:
            await self._hass.async_add_executor_job(remove_media, filename)
        except OSError as err:
            _LOGGER.error("Unable to remove media file: %s %s", filename, err)

    async def _get_devices(self) -> Mapping[str, str]:
        """Return a mapping of nest device id to home assistant device id."""
        device_registry = dr.async_get(self._hass)
        device_manager = await self._subscriber.async_get_device_manager()
        devices = {}
        for device in device_manager.devices.values():
            if device_entry := device_registry.async_get_device(
                identifiers={(DOMAIN, device.name)}
            ):
                devices[device.name] = device_entry.id
        return devices


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up Nest media source."""
    return NestMediaSource(hass)


@callback
def async_get_media_source_devices(hass: HomeAssistant) -> Mapping[str, Device]:
    """Return a mapping of device id to eligible Nest event media devices."""
    devices = async_nest_devices_by_device_id(hass)
    return {
        device_id: device
        for device_id, device in devices.items()
        if CameraEventImageTrait.NAME in device.traits
        or CameraClipPreviewTrait.NAME in device.traits
    }


@dataclass
class MediaId:
    """Media identifier for a node in the Media Browse tree.

    A MediaId can refer to either a device, or a specific event for a device
    that is associated with media (e.g. image or video clip).
    """

    device_id: str
    event_token: str | None = None

    @property
    def identifier(self) -> str:
        """Media identifier represented as a string."""
        if self.event_token:
            return f"{self.device_id}/{self.event_token}"
        return self.device_id


def parse_media_id(identifier: str | None = None) -> MediaId | None:
    """Parse the identifier path string into a MediaId."""
    if identifier is None or identifier == "":
        return None
    parts = identifier.split("/")
    if len(parts) > 1:
        return MediaId(parts[0], parts[1])
    return MediaId(parts[0])


class NestMediaSource(MediaSource):
    """Provide Nest Media Sources for Nest Cameras.

    The media source generates a directory tree of devices and media associated
    with events for each device (e.g. motion, person, etc). Each node in the
    tree has a unique MediaId.

    The lifecycle for event media is handled outside of NestMediaSource, and
    instead it just asks the device for all events it knows about.
    """

    name: str = MEDIA_SOURCE_TITLE

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize NestMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media identifier to a url."""
        media_id: MediaId | None = parse_media_id(item.identifier)
        if not media_id:
            raise Unresolvable("No identifier specified for MediaSourceItem")
        devices = async_get_media_source_devices(self.hass)
        if not (device := devices.get(media_id.device_id)):
            raise Unresolvable(
                f"Unable to find device with identifier: {item.identifier}"
            )
        if not media_id.event_token:
            # The device resolves to the most recent event if available
            if not (
                last_event_id := await _async_get_recent_event_id(media_id, device)
            ):
                raise Unresolvable(
                    f"Unable to resolve recent event for device: {item.identifier}"
                )
            media_id = last_event_id

        # Infer content type from the device, since it only supports one
        # snapshot type (either jpg or mp4 clip)
        content_type = EventImageType.IMAGE.content_type
        if CameraClipPreviewTrait.NAME in device.traits:
            content_type = EventImageType.CLIP_PREVIEW.content_type
        return PlayMedia(
            EVENT_MEDIA_API_URL_FORMAT.format(
                device_id=media_id.device_id, event_token=media_id.event_token
            ),
            content_type,
        )

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return media for the specified level of the directory tree.

        The top level is the root that contains devices. Inside each device are
        media for events for that device.
        """
        media_id: MediaId | None = parse_media_id(item.identifier)
        _LOGGER.debug(
            "Browsing media for identifier=%s, media_id=%s", item.identifier, media_id
        )
        devices = async_get_media_source_devices(self.hass)
        if media_id is None:
            # Browse the root and return child devices
            browse_root = _browse_root()
            browse_root.children = []
            for device_id, child_device in devices.items():
                browse_device = _browse_device(MediaId(device_id), child_device)
                if last_event_id := await _async_get_recent_event_id(
                    MediaId(device_id), child_device
                ):
                    browse_device.thumbnail = EVENT_THUMBNAIL_URL_FORMAT.format(
                        device_id=last_event_id.device_id,
                        event_token=last_event_id.event_token,
                    )
                    browse_device.can_play = True
                browse_root.children.append(browse_device)
            return browse_root

        # Browse either a device or events within a device
        if not (device := devices.get(media_id.device_id)):
            raise BrowseError(
                f"Unable to find device with identiifer: {item.identifier}"
            )
        # Clip previews are a session with multiple possible event types (e.g.
        # person, motion, etc) and a single mp4
        if CameraClipPreviewTrait.NAME in device.traits:
            clips: dict[
                str, ClipPreviewSession
            ] = await _async_get_clip_preview_sessions(device)
            if media_id.event_token is None:
                # Browse a specific device and return child events
                browse_device = _browse_device(media_id, device)
                browse_device.children = []
                for clip in clips.values():
                    event_id = MediaId(media_id.device_id, clip.event_token)
                    browse_device.children.append(
                        _browse_clip_preview(event_id, device, clip)
                    )
                return browse_device

            # Browse a specific event
            if not (single_clip := clips.get(media_id.event_token)):
                raise BrowseError(
                    f"Unable to find event with identiifer: {item.identifier}"
                )
            return _browse_clip_preview(media_id, device, single_clip)

        # Image events are 1:1 of media to event
        images: dict[str, ImageSession] = await _async_get_image_sessions(device)
        if media_id.event_token is None:
            # Browse a specific device and return child events
            browse_device = _browse_device(media_id, device)
            browse_device.children = []
            for image in images.values():
                event_id = MediaId(media_id.device_id, image.event_token)
                browse_device.children.append(
                    _browse_image_event(event_id, device, image)
                )
            return browse_device

        # Browse a specific event
        if not (single_image := images.get(media_id.event_token)):
            raise BrowseError(
                f"Unable to find event with identiifer: {item.identifier}"
            )
        return _browse_image_event(media_id, device, single_image)


async def _async_get_clip_preview_sessions(
    device: Device,
) -> dict[str, ClipPreviewSession]:
    """Return clip preview sessions for the device."""
    events = await device.event_media_manager.async_clip_preview_sessions()
    return {e.event_token: e for e in events}


async def _async_get_image_sessions(device: Device) -> dict[str, ImageSession]:
    """Return image events for the device."""
    events = await device.event_media_manager.async_image_sessions()
    return {e.event_token: e for e in events}


def _browse_root() -> BrowseMediaSource:
    """Return devices in the root."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier="",
        media_class=MediaClass.DIRECTORY,
        media_content_type=MediaType.VIDEO,
        children_media_class=MediaClass.VIDEO,
        title=MEDIA_SOURCE_TITLE,
        can_play=False,
        can_expand=True,
        thumbnail=None,
        children=[],
    )


async def _async_get_recent_event_id(
    device_id: MediaId, device: Device
) -> MediaId | None:
    """Return thumbnail for most recent device event."""
    if CameraClipPreviewTrait.NAME in device.traits:
        clips = await device.event_media_manager.async_clip_preview_sessions()
        if not clips:
            return None
        return MediaId(device_id.device_id, next(iter(clips)).event_token)
    images = await device.event_media_manager.async_image_sessions()
    if not images:
        return None
    return MediaId(device_id.device_id, next(iter(images)).event_token)


def _browse_device(device_id: MediaId, device: Device) -> BrowseMediaSource:
    """Return details for the specified device."""
    device_info = NestDeviceInfo(device)
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=device_id.identifier,
        media_class=MediaClass.DIRECTORY,
        media_content_type=MediaType.VIDEO,
        children_media_class=MediaClass.VIDEO,
        title=DEVICE_TITLE_FORMAT.format(device_name=device_info.device_name),
        can_play=False,
        can_expand=True,
        thumbnail=None,
        children=[],
    )


def _browse_clip_preview(
    event_id: MediaId, device: Device, event: ClipPreviewSession
) -> BrowseMediaSource:
    """Build a BrowseMediaSource for a specific clip preview event."""
    types = [
        MEDIA_SOURCE_EVENT_TITLE_MAP.get(event_type, "Event")
        for event_type in event.event_types
    ]
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=event_id.identifier,
        media_class=MediaClass.IMAGE,
        media_content_type=MediaType.IMAGE,
        title=CLIP_TITLE_FORMAT.format(
            event_name=", ".join(types),
            event_time=dt_util.as_local(event.timestamp).strftime(DATE_STR_FORMAT),
        ),
        can_play=True,
        can_expand=False,
        thumbnail=EVENT_THUMBNAIL_URL_FORMAT.format(
            device_id=event_id.device_id, event_token=event_id.event_token
        ),
        children=[],
    )


def _browse_image_event(
    event_id: MediaId, device: Device, event: ImageSession
) -> BrowseMediaSource:
    """Build a BrowseMediaSource for a specific image event."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=event_id.identifier,
        media_class=MediaClass.IMAGE,
        media_content_type=MediaType.IMAGE,
        title=CLIP_TITLE_FORMAT.format(
            event_name=MEDIA_SOURCE_EVENT_TITLE_MAP.get(event.event_type, "Event"),
            event_time=dt_util.as_local(event.timestamp).strftime(DATE_STR_FORMAT),
        ),
        can_play=False,
        can_expand=False,
        thumbnail=EVENT_THUMBNAIL_URL_FORMAT.format(
            device_id=event_id.device_id, event_token=event_id.event_token
        ),
        children=[],
    )
