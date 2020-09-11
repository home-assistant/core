"""This component provides support for SimpliSafe cameras."""
import asyncio

from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from simplipy.system import SystemStates

from homeassistant.components.camera import Camera
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream

from . import SimpliSafeEntity
from .const import DATA_CLIENT, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SimpliCam cameras based on a config entry."""
    simplisafe = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    cameras = []
    for system in simplisafe.systems.values():
        if (
            "cameras" in system._location_info["system"]
            and len(system._location_info["system"]["cameras"]) > 0
        ):
            for cam in system._location_info["system"]["cameras"]:
                cameras.append(cam)

    async_add_entities(
        [
            SimpliCam(simplisafe, system, hass.data[DATA_FFMPEG], camera)
            for camera in cameras
        ]
    )


class SimpliCam(SimpliSafeEntity, Camera):
    """An implementation of a SimpliCam camera."""

    def __init__(self, simplisafe, system, ffmpeg, camera):
        """Initialize a SimpliCam camera."""
        Camera.__init__(self)
        super().__init__(
            simplisafe,
            system,
            camera["cameraSettings"]["cameraName"],
            serial=camera["uuid"],
        )

        self._simplisafe = simplisafe
        self._system = system
        self._camera = camera
        self._ffmpeg = ffmpeg
        self._last_image = None

        self._is_online = self._camera["status"] == "online"
        self._is_subscribed = self._camera["subscription"]["enabled"]

    @property
    def unique_id(self):
        """Return unique ID of camera."""
        return "{}-camera".format(self._camera["uuid"])

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._camera["uuid"])},
            "manufacturer": "SimpliSafe",
            "model": self._camera["model"],
            "name": self._camera["cameraSettings"]["cameraName"],
            "via_device": (DOMAIN, self._system.serial),
        }

    @property
    def is_on(self):
        """Return true if on."""
        return self._is_online and self._is_subscribed

    @callback
    def async_update_from_rest_api(self):
        """Update the entity with the provided REST API data."""
        self._is_online = self._camera["status"] == "online"
        self._is_subscribed = self._camera["subscription"]["enabled"]

    @property
    def _video_url(self):
        """Provide the video URL."""
        return '{} -i "https://media.simplisafe.com/v1/{}/flv?x=1280&audioEncoding=AAC"'.format(
            self.auth_headers, self._camera["uuid"]
        )

    @property
    def auth_headers(self):
        """Generate auth headers."""
        return '-headers "Authorization: Bearer {}"'.format(
            self._simplisafe._api.access_token
        )

    @property
    def is_shutter_open(self):
        """Check if the camera shutter is open."""
        if self._system.state == SystemStates.off:
            return self._camera["cameraSettings"]["shutterOff"] == "open"
        if self._system.state == SystemStates.home:
            return self._camera["cameraSettings"]["shutterHome"] == "open"
        if self._system.state == SystemStates.away:
            return self._camera["cameraSettings"]["shutterAway"] == "open"
        return True

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        if not self.is_shutter_open:
            """Shutter is currently closed, return last image."""
            return self._last_image

        ffmpeg = ImageFrame(self._ffmpeg.binary, loop=self.hass.loop)

        if self._video_url is None:
            return

        image = await asyncio.shield(
            ffmpeg.get_image(
                self._video_url,
                output_format=IMAGE_JPEG,
            )
        )
        self._last_image = image
        return image

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        if self._video_url is None:
            return

        stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
        await stream.open_camera(
            self._video_url,
        )

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                self._ffmpeg.ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()
