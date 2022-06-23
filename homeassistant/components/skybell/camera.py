"""Camera support for the Skybell HD Doorbell."""
from __future__ import annotations

from aiohttp import web
from haffmpeg.camera import CameraMjpeg
import voluptuous as vol

from homeassistant.components.camera import (
    PLATFORM_SCHEMA,
    Camera,
    CameraEntityDescription,
)
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ACTIVITY_NAME,
    CONF_AVATAR_NAME,
    DOMAIN,
    IMAGE_ACTIVITY,
    IMAGE_AVATAR,
)
from .coordinator import SkybellDataUpdateCoordinator
from .entity import SkybellEntity

# Deprecated in Home Assistant 2022.6
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[IMAGE_AVATAR]): vol.All(
            cv.ensure_list, [vol.In([IMAGE_AVATAR, IMAGE_ACTIVITY])]
        ),
        vol.Optional(CONF_ACTIVITY_NAME): cv.string,
        vol.Optional(CONF_AVATAR_NAME): cv.string,
    }
)

CAMERA_TYPES: tuple[CameraEntityDescription, ...] = (
    CameraEntityDescription(key="activity", name="Last Activity"),
    CameraEntityDescription(key="avatar", name="Camera"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Skybell switch."""
    entities = []
    for description in CAMERA_TYPES:
        for coordinator in hass.data[DOMAIN][entry.entry_id]:
            if description.key == "avatar":
                entities.append(SkybellCamera(coordinator, description))
            else:
                entities.append(SkybellActivityCamera(coordinator, description))
    async_add_entities(entities)


class SkybellCamera(SkybellEntity, Camera):
    """A camera implementation for Skybell devices."""

    def __init__(
        self,
        coordinator: SkybellDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize a camera for a Skybell device."""
        super().__init__(coordinator, description)
        Camera.__init__(self)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Get the latest camera image."""
        return self._device.images[self.entity_description.key]


class SkybellActivityCamera(SkybellCamera):
    """A camera implementation for latest Skybell activity."""

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse:
        """Generate an HTTP MJPEG stream from the latest recorded activity."""
        stream = CameraMjpeg(get_ffmpeg_manager(self.hass).binary)
        url = await self.coordinator.device.async_get_activity_video_url()
        await stream.open_camera(url, extra_cmd="-r 210")

        try:
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                await stream.get_reader(),
                get_ffmpeg_manager(self.hass).ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()
