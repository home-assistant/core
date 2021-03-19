"""The motionEye integration."""
from typing import Callable

from motioneye_client.const import (
    KEY_CAMERAS,
    KEY_ID,
    KEY_NAME,
    KEY_STREAMING_PORT,
    KEY_VIDEO_STREAMING,
)
from motioneye_client.utils import compute_signature_from_password

from homeassistant.components.mjpeg.camera import (
    CONF_MJPEG_URL,
    CONF_STILL_IMAGE_URL,
    CONF_VERIFY_SSL,
    MjpegCamera,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import get_motioneye_unique_id
from .const import (
    CONF_COORDINATOR,
    CONF_ON_UNLOAD,
    DOMAIN,
    SIGNAL_ENTITY_REMOVE,
    TYPE_MOTIONEYE_MJPEG_CAMERA,
)

PLATFORMS = ["camera"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> bool:
    """Set up motionEye from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data[CONF_COORDINATOR]
    current_camera_ids = set()

    async def add_camera_entities():
        if KEY_CAMERAS not in coordinator.data:
            return True
        cameras = coordinator.data[KEY_CAMERAS]
        refreshed_camera_ids = set()
        entities_to_add = []

        for camera in cameras:
            if (
                camera.get(KEY_ID) is None
                or not camera.get(KEY_VIDEO_STREAMING, False)
                or KEY_STREAMING_PORT not in camera
                or KEY_NAME not in camera
            ):
                continue
            camera_id = camera[KEY_ID]
            stream_port = camera[KEY_STREAMING_PORT]

            refreshed_camera_ids.add(camera_id)
            if camera_id in current_camera_ids:
                continue
            current_camera_ids.add(camera_id)
            entities_to_add.append(
                MotionEyeMjpegCamera(
                    entry.data[CONF_HOST],
                    entry.data[CONF_PORT],
                    stream_port,
                    entry.data[CONF_USERNAME],
                    entry.data.get(CONF_PASSWORD),
                    HTTP_BASIC_AUTHENTICATION,  # TODO Add auth options.
                    camera[KEY_NAME],
                    camera_id,
                    coordinator,
                )
            )

        async_add_entities(entities_to_add)

        removed_cameras = current_camera_ids - refreshed_camera_ids
        for camera_id in removed_cameras:
            current_camera_ids.remove(camera_id)
            async_dispatcher_send(
                hass,
                SIGNAL_ENTITY_REMOVE.format(
                    get_motioneye_unique_id(
                        entry.data[CONF_HOST],
                        entry.data[CONF_PORT],
                        camera_id,
                        TYPE_MOTIONEYE_MJPEG_CAMERA,
                    ),
                ),
            )

    await add_camera_entities()
    entry_data[CONF_ON_UNLOAD].append(
        coordinator.async_add_listener(add_camera_entities)
    )
    return True


class MotionEyeMjpegCamera(MjpegCamera, CoordinatorEntity):
    """motionEye mjpeg camera."""

    def __init__(
        self,
        host: str,
        port: int,
        stream_port: int,
        username: str,
        password: str,
        auth: str,
        name: str,
        camera_id: int,
        coordinator: DataUpdateCoordinator,
    ):
        """Initialize a MJPEG camera."""
        self._unique_id = get_motioneye_unique_id(host, port, camera_id, name)
        still_image_url = (
            f"http://{host}:{port}/picture/{camera_id}/current/?_username={username}"
        )
        signature = compute_signature_from_password(
            "GET", still_image_url, None, password
        )
        still_image_url += f"&_signature={signature}"

        MjpegCamera.__init__(
            self,
            {
                CONF_NAME: name,
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_MJPEG_URL: f"http://{host}:{stream_port}/",
                CONF_STILL_IMAGE_URL: still_image_url,
                CONF_AUTHENTICATION: auth,
                CONF_VERIFY_SSL: False,
            },
        )
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def unique_id(self) -> str:
        """Return a unique id for this instance."""
        return self._unique_id

    # TODO add state attribute.
