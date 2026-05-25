"""Support for SimpliSafe cameras."""

from typing import TYPE_CHECKING, cast

from simplipy.device import DeviceTypes
from simplipy.device.sensor.v3 import SensorV3
from simplipy.errors import SimplipyError
from simplipy.system.v3 import SystemV3
from simplipy.websocket import EVENT_CAMERA_MOTION_DETECTED, WebsocketEvent

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DEFAULT_IMAGE_WIDTH, SimpliSafe, SimpliSafeConfigEntry, _resolve_image_url
from .const import LOGGER
from .entity import SimpliSafeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SimpliSafeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SimpliSafe cameras based on a config entry."""
    simplisafe = entry.runtime_data

    cameras: list[SimplisafeCamera] = []
    for system in simplisafe.systems.values():
        if system.version == 2:
            LOGGER.warning("Skipping camera setup for V2 system: %s", system.system_id)
            continue

        if TYPE_CHECKING:
            assert isinstance(system, SystemV3)
        found = [
            sensor
            for sensor in system.sensors.values()
            if sensor.type == DeviceTypes.OUTDOOR_CAMERA
        ]
        LOGGER.debug(
            "System %s: found %d outdoor camera(s): %s",
            system.system_id,
            len(found),
            [s.serial for s in found],
        )
        cameras.extend(
            SimplisafeCamera(simplisafe, system, cast(SensorV3, sensor))
            for sensor in found
        )

    async_add_entities(cameras)


class SimplisafeCamera(SimpliSafeEntity, Camera):
    """A SimpliSafe outdoor camera."""

    _device: SensorV3

    def __init__(
        self,
        simplisafe: SimpliSafe,
        system: SystemV3,
        sensor: SensorV3,
    ) -> None:
        """Initialize."""
        SimpliSafeEntity.__init__(
            self,
            simplisafe,
            system,
            device=sensor,
            additional_websocket_events=[EVENT_CAMERA_MOTION_DETECTED],
        )
        Camera.__init__(self)

    @callback
    def async_update_from_websocket_event(self, event: WebsocketEvent) -> None:
        """Update the entity when new data comes from the websocket."""
        if event.media_urls is not None:
            LOGGER.debug(
                "Camera %s (serial %s) motion detected; caching media URLs",
                self.name,
                self._device.serial,
            )
            self._simplisafe.camera_media_urls[self._device.serial] = event.media_urls
        else:
            LOGGER.debug(
                "Camera %s (serial %s) motion event received with no media URLs",
                self.name,
                self._device.serial,
            )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the last captured motion image."""
        media_urls = self._simplisafe.camera_media_urls.get(self._device.serial)
        if media_urls is None:
            return None
        try:
            return await self._simplisafe.async_media(
                _resolve_image_url(
                    media_urls["image_url"],
                    width if width is not None else DEFAULT_IMAGE_WIDTH,
                )
            )
        except SimplipyError as err:
            raise HomeAssistantError(
                f"Error fetching camera image for {self.name}: {err}"
            ) from err
