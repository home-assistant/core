"""Support for viewing the camera feed from a DoorBird video doorbell."""

import datetime
import logging
from typing import override

import aiohttp

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .deprecation import deprecate_entity
from .entity import DoorBirdEntity
from .models import DoorBirdConfigEntry, DoorBirdData
from .util import get_mac_address_from_door_station_info

_LAST_VISITOR_INTERVAL = datetime.timedelta(minutes=2)
_LAST_MOTION_INTERVAL = datetime.timedelta(seconds=30)
_LIVE_INTERVAL = datetime.timedelta(seconds=45)
_LOGGER = logging.getLogger(__name__)
_TIMEOUT = 15  # seconds


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DoorBirdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DoorBird camera platform."""
    door_bird_data = config_entry.runtime_data
    device = door_bird_data.door_station.device
    mac_addr = get_mac_address_from_door_station_info(door_bird_data.door_station_info)
    entity_registry = er.async_get(hass)

    entities = [
        DoorBirdCamera(
            door_bird_data,
            device.live_image_url,
            "live",
            _LIVE_INTERVAL,
            device.rtsp_live_video_url,
        )
    ]

    # Without events nothing can invalidate the images, which do not poll, so
    # the replacement would freeze on its first fetch. Keep these until the
    # entry configures an event.
    events_configured = any(door_bird_data.door_station.events)

    for camera_id, history_type, interval in (
        ("last_ring", "doorbell", _LAST_VISITOR_INTERVAL),
        ("last_motion", "motionsensor", _LAST_MOTION_INTERVAL),
    ):
        if events_configured and not deprecate_entity(
            hass,
            entity_registry,
            platform_domain=Platform.CAMERA,
            entity_unique_id=f"{mac_addr}_{camera_id}",
            issue_id=f"deprecated_camera_{mac_addr}_{camera_id}",
            translation_key=f"deprecated_camera_{camera_id}",
        ):
            continue
        entities.append(
            DoorBirdCamera(
                door_bird_data,
                device.history_image_url(1, history_type),
                camera_id,
                interval,
            )
        )

    async_add_entities(entities)


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
        self._interval = interval
        self._last_update = datetime.datetime.min
        self._attr_unique_id = f"{self._mac_addr}_{camera_id}"

    @override
    async def stream_source(self) -> str | None:
        """Return the stream source."""
        return self._stream_url

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
