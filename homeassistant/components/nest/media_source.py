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

from google_nest_sdm.camera_traits import CameraClipPreviewTrait, CameraEventImageTrait
from google_nest_sdm.device import Device
from google_nest_sdm.event import EventImageType, ImageEventBase

from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_IMAGE,
    MEDIA_CLASS_VIDEO,
    MEDIA_TYPE_IMAGE,
    MEDIA_TYPE_VIDEO,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.components.nest.const import DATA_SUBSCRIBER, DOMAIN
from homeassistant.components.nest.device_info import NestDeviceInfo
from homeassistant.components.nest.events import MEDIA_SOURCE_EVENT_TITLE_MAP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

MEDIA_SOURCE_TITLE = "Nest"
DEVICE_TITLE_FORMAT = "{device_name}: Recent Events"
CLIP_TITLE_FORMAT = "{event_name} @ {event_time}"
EVENT_MEDIA_API_URL_FORMAT = "/api/nest/event_media/{device_id}/{event_id}"


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up Nest media source."""
    return NestMediaSource(hass)


async def get_media_source_devices(hass: HomeAssistant) -> Mapping[str, Device]:
    """Return a mapping of device id to eligible Nest event media devices."""
    if DATA_SUBSCRIBER not in hass.data[DOMAIN]:
        # Integration unloaded, or is legacy nest integration
        return {}
    subscriber = hass.data[DOMAIN][DATA_SUBSCRIBER]
    device_manager = await subscriber.async_get_device_manager()
    device_registry = await hass.helpers.device_registry.async_get_registry()
    devices = {}
    for device in device_manager.devices.values():
        if not (
            CameraEventImageTrait.NAME in device.traits
            or CameraClipPreviewTrait.NAME in device.traits
        ):
            continue
        if device_entry := device_registry.async_get_device({(DOMAIN, device.name)}):
            devices[device_entry.id] = device
    return devices


@dataclass
class MediaId:
    """Media identifier for a node in the Media Browse tree.

    A MediaId can refer to either a device, or a specific event for a device
    that is associated with media (e.g. image or video clip).
    """

    device_id: str
    event_id: str | None = None

    @property
    def identifier(self) -> str:
        """Media identifier represented as a string."""
        if self.event_id:
            return f"{self.device_id}/{self.event_id}"
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
        if not media_id.event_id:
            raise Unresolvable("Identifier missing an event_id: %s" % item.identifier)
        devices = await self.devices()
        if not (device := devices.get(media_id.device_id)):
            raise Unresolvable(
                "Unable to find device with identifier: %s" % item.identifier
            )
        events = await _get_events(device)
        if media_id.event_id not in events:
            raise Unresolvable(
                "Unable to find event with identifier: %s" % item.identifier
            )
        event = events[media_id.event_id]
        return PlayMedia(
            EVENT_MEDIA_API_URL_FORMAT.format(
                device_id=media_id.device_id, event_id=media_id.event_id
            ),
            event.event_image_type.content_type,
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
        devices = await self.devices()
        if media_id is None:
            # Browse the root and return child devices
            browse_root = _browse_root()
            browse_root.children = []
            for device_id, child_device in devices.items():
                browse_root.children.append(
                    _browse_device(MediaId(device_id), child_device)
                )
            return browse_root

        # Browse either a device or events within a device
        if not (device := devices.get(media_id.device_id)):
            raise BrowseError(
                "Unable to find device with identiifer: %s" % item.identifier
            )
        if media_id.event_id is None:
            # Browse a specific device and return child events
            browse_device = _browse_device(media_id, device)
            browse_device.children = []
            events = await _get_events(device)
            for child_event in events.values():
                event_id = MediaId(media_id.device_id, child_event.event_session_id)
                browse_device.children.append(
                    _browse_event(event_id, device, child_event)
                )
            return browse_device

        # Browse a specific event
        events = await _get_events(device)
        if not (event := events.get(media_id.event_id)):
            raise BrowseError(
                "Unable to find event with identiifer: %s" % item.identifier
            )
        return _browse_event(media_id, device, event)

    async def devices(self) -> Mapping[str, Device]:
        """Return all event media related devices."""
        return await get_media_source_devices(self.hass)


async def _get_events(device: Device) -> Mapping[str, ImageEventBase]:
    """Return relevant events for the specified device."""
    events = await device.event_media_manager.async_events()
    return {e.event_session_id: e for e in events}


def _browse_root() -> BrowseMediaSource:
    """Return devices in the root."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier="",
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_type=MEDIA_TYPE_VIDEO,
        children_media_class=MEDIA_CLASS_VIDEO,
        title=MEDIA_SOURCE_TITLE,
        can_play=False,
        can_expand=True,
        thumbnail=None,
        children=[],
    )


def _browse_device(device_id: MediaId, device: Device) -> BrowseMediaSource:
    """Return details for the specified device."""
    device_info = NestDeviceInfo(device)
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=device_id.identifier,
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_type=MEDIA_TYPE_VIDEO,
        children_media_class=MEDIA_CLASS_VIDEO,
        title=DEVICE_TITLE_FORMAT.format(device_name=device_info.device_name),
        can_play=False,
        can_expand=True,
        thumbnail=None,
        children=[],
    )


def _browse_event(
    event_id: MediaId, device: Device, event: ImageEventBase
) -> BrowseMediaSource:
    """Build a BrowseMediaSource for a specific event."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=event_id.identifier,
        media_class=MEDIA_CLASS_IMAGE,
        media_content_type=MEDIA_TYPE_IMAGE,
        title=CLIP_TITLE_FORMAT.format(
            event_name=MEDIA_SOURCE_EVENT_TITLE_MAP.get(event.event_type, "Event"),
            event_time=dt_util.as_local(event.timestamp).strftime(DATE_STR_FORMAT),
        ),
        can_play=(event.event_image_type == EventImageType.CLIP_PREVIEW),
        can_expand=False,
        thumbnail=None,
        children=[],
    )
