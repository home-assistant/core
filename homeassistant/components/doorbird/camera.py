"""Support for viewing the camera feed from a DoorBird video doorbell."""

import datetime
import logging
import re
from typing import override

import aiohttp

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .entity import DoorBirdEntity
from .models import DoorBirdConfigEntry, DoorBirdData

_LAST_VISITOR_INTERVAL = datetime.timedelta(minutes=2)
_LAST_MOTION_INTERVAL = datetime.timedelta(seconds=30)
_LIVE_INTERVAL = datetime.timedelta(seconds=45)
_LOGGER = logging.getLogger(__name__)
_TIMEOUT = 15  # seconds
_PASSWORD_IN_URL = re.compile(r"(://[^:/@\s]+:)[^@\s]*@")


def _get_backchannel_source(transmit_url: str) -> str:
    """Return the go2rtc source that transmits audio to the device.

    ffmpeg reads the G.711 µ-law audio go2rtc writes to its stdin and posts it
    to the audio-transmit endpoint with Content-Type audio/basic.
    """
    # Stream one plain body right away: preemptive basic auth, no 100-continue,
    # no chunked encoding, like go2rtc's own DoorBird source
    return (
        "exec:ffmpeg -hide_banner -f mulaw -ar 8000 -ac 1 -i - -c:a copy"
        " -f mulaw -flush_packets 1 -method POST -content_type audio/basic"
        " -auth_type basic -send_expect_100 0 -icy 0 -chunked_post 0"
        ' -headers "Content-Length: 9999999"'
        f" {transmit_url}#backchannel=1#audio=pcmu/8000"
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DoorBirdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DoorBird camera platform."""
    door_bird_data = config_entry.runtime_data
    device = door_bird_data.door_station.device

    async_add_entities(
        [
            DoorBirdCamera(
                door_bird_data,
                device.live_image_url,
                "live",
                _LIVE_INTERVAL,
                device.rtsp_live_video_url,
            ),
            DoorBirdCamera(
                door_bird_data,
                device.history_image_url(1, "doorbell"),
                "last_ring",
                _LAST_VISITOR_INTERVAL,
            ),
            DoorBirdCamera(
                door_bird_data,
                device.history_image_url(1, "motionsensor"),
                "last_motion",
                _LAST_MOTION_INTERVAL,
            ),
        ]
    )


class DoorBirdCamera(DoorBirdEntity, Camera):
    """The camera on a DoorBird device."""

    def __init__(
        self,
        door_bird_data: DoorBirdData,
        url: str,
        camera_id: str,
        interval: datetime.timedelta,
        stream_url: str | None = None,
    ) -> None:
        """Initialize the camera on a DoorBird device."""
        super().__init__(door_bird_data)
        self._url = url
        self._stream_url = stream_url
        self._attr_translation_key = camera_id
        self._last_image: bytes | None = None
        if self._stream_url:
            self._attr_supported_features = CameraEntityFeature.STREAM
            self._attr_supports_two_way_audio = True
        self._interval = interval
        self._last_update = datetime.datetime.min
        self._attr_unique_id = f"{self._mac_addr}_{camera_id}"

    @override
    async def stream_source(self) -> str | None:
        """Return the stream source."""
        return self._stream_url

    @override
    async def additional_stream_sources(self) -> list[str]:
        """Return the audio and two way audio sources, as RTSP has no audio."""
        if not self._stream_url:
            return []
        device = self._door_station.device
        sources = [
            device.live_audio_url,
            _get_backchannel_source(device.live_audio_transmit_url),
        ]
        if _LOGGER.isEnabledFor(logging.DEBUG):
            audio, backchannel = (
                _PASSWORD_IN_URL.sub(r"\1***@", source) for source in sources
            )
            _LOGGER.debug(
                "%s audio source: %s, two way audio source: %s",
                self.entity_id,
                audio,
                backchannel,
            )
        return sources

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Pull a still image from the camera."""
        now = dt_util.utcnow()

        if self._last_image and now - self._last_update < self._interval:
            return self._last_image

        try:
            self._last_image = await self._door_station.device.get_image(
                self._url, timeout=_TIMEOUT
            )
        # pylint: disable-next=home-assistant-action-swallowed-exception
        except TimeoutError:
            _LOGGER.error("DoorBird %s: Camera image timed out", self.name)
            return self._last_image
        except aiohttp.ClientError as error:
            _LOGGER.error(
                "DoorBird %s: Error getting camera image: %s", self.name, error
            )
            return self._last_image

        self._last_update = now
        return self._last_image

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to events."""
        await super().async_added_to_hass()
        event_to_entity_id = self._door_bird_data.event_entity_ids
        for event in self._door_station.door_station_events:
            event_to_entity_id[event] = self.entity_id

    @callback
    @override
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Update the entity_id reported in events owned by this camera."""
        super().async_entity_id_changed(old_entity_id)
        event_to_entity_id = self._door_bird_data.event_entity_ids
        for event in self._door_station.door_station_events:
            if event_to_entity_id.get(event) == old_entity_id:
                event_to_entity_id[event] = self.entity_id

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from events."""
        event_to_entity_id = self._door_bird_data.event_entity_ids
        for event in self._door_station.door_station_events:
            # If the clear api was called, the events may not be in the dict
            event_to_entity_id.pop(event, None)
        await super().async_will_remove_from_hass()
