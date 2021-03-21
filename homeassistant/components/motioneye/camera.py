"""The motionEye integration."""
import functools
import logging
from typing import Any, Callable, Dict

from motioneye_client.client import MotionEyeClient
from motioneye_client.const import (
    DEFAULT_USERNAME_SURVEILLANCE,
    KEY_CAMERAS,
    KEY_ID,
    KEY_NAME,
    KEY_STREAMING_AUTH_MODE,
)

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
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import get_camera_from_cameras_data, get_motioneye_unique_id
from .const import (
    CONF_CLIENT,
    CONF_COORDINATOR,
    CONF_ON_UNLOAD,
    CONF_PASSWORD_SURVEILLANCE,
    CONF_USERNAME_SURVEILLANCE,
    DOMAIN,
    SIGNAL_ENTITY_REMOVE,
    TYPE_MOTIONEYE_MJPEG_CAMERA,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> bool:
    """Set up motionEye from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data[CONF_COORDINATOR]
    current_camera_ids = set()

    def add_camera_entities():
        if KEY_CAMERAS not in coordinator.data:
            return True
        cameras = coordinator.data[KEY_CAMERAS]
        refreshed_camera_ids = set()
        entities_to_add = []

        for camera in cameras:
            if (
                camera.get(KEY_ID) is None
                or KEY_NAME not in camera
                or not MotionEyeClient.is_camera_streaming(camera)
            ):
                continue
            camera_id = camera[KEY_ID]
            refreshed_camera_ids.add(camera_id)
            if camera_id in current_camera_ids:
                continue
            current_camera_ids.add(camera_id)
            entities_to_add.append(
                MotionEyeMjpegCamera(
                    entry.data[CONF_HOST],
                    entry.data[CONF_PORT],
                    entry.data.get(CONF_USERNAME_SURVEILLANCE)
                    or DEFAULT_USERNAME_SURVEILLANCE,
                    entry.data.get(CONF_PASSWORD_SURVEILLANCE) or "",
                    camera,
                    entry_data[CONF_CLIENT],
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

    add_camera_entities()
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
        username: str,
        password: str,
        camera: Dict[str, Any],
        client: MotionEyeClient,
        coordinator: DataUpdateCoordinator,
    ):
        """Initialize a MJPEG camera."""
        self._camera_id = camera[KEY_ID]
        self._unique_id = get_motioneye_unique_id(
            host, port, self._camera_id, TYPE_MOTIONEYE_MJPEG_CAMERA
        )
        self._client = client

        auth = None
        if camera[KEY_STREAMING_AUTH_MODE] in [
            HTTP_BASIC_AUTHENTICATION,
            HTTP_DIGEST_AUTHENTICATION,
        ]:
            auth = camera[KEY_STREAMING_AUTH_MODE]

        MjpegCamera.__init__(
            self,
            {
                CONF_NAME: camera[KEY_NAME],
                CONF_USERNAME: username if auth is not None else None,
                CONF_PASSWORD: password if auth is not None else None,
                CONF_MJPEG_URL: client.get_camera_steam_url(camera),
                CONF_STILL_IMAGE_URL: client.get_camera_snapshot_url(camera),
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

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity added to hass."""
        await super().async_added_to_hass()
        assert self.hass
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ENTITY_REMOVE.format(self.unique_id),
                functools.partial(self.async_remove, force_remove=True),
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.last_update_success:
            camera = get_camera_from_cameras_data(
                self._camera_id, self.coordinator.data
            )
            if camera:
                self._still_image_url = self._client.get_camera_snapshot_url(camera)
                self._mjpeg_url = self._client.get_camera_steam_url(camera)
                # TODO: update auth if auth value in camera changes.
        CoordinatorEntity._handle_coordinator_update(self)
