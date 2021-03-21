"""The motionEye integration."""
import functools
import logging
from typing import Any, Callable, Dict, Set

import aiohttp
from motioneye_client.client import MotionEyeClient
from motioneye_client.const import (
    DEFAULT_USERNAME_SURVEILLANCE,
    KEY_CAMERAS,
    KEY_ID,
    KEY_MOTION_DETECTION,
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

from . import get_camera_from_cameras, get_motioneye_unique_id
from .const import (
    CONF_CLIENT,
    CONF_COORDINATOR,
    CONF_ON_UNLOAD,
    CONF_PASSWORD_SURVEILLANCE,
    CONF_USERNAME_SURVEILLANCE,
    DOMAIN,
    MOTIONEYE_MANUFACTURER,
    SIGNAL_ENTITY_REMOVE,
    TYPE_MOTIONEYE_MJPEG_CAMERA,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera"]


def _is_acceptable_camera(camera: Dict[str, Any]) -> bool:
    """Determine if a camera dict is acceptable."""
    return (
        camera
        and KEY_ID in camera
        and KEY_NAME in camera
        and KEY_STREAMING_AUTH_MODE in camera
        and MotionEyeClient.is_camera_streaming(camera)
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> bool:
    """Set up motionEye from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data[CONF_COORDINATOR]
    current_camera_ids = set()

    def _remove_cameras(remove_ids: Set[int]):
        for camera_id in remove_ids:
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

    def _process_camera_entities():
        if KEY_CAMERAS not in coordinator.data:
            return True
        cameras = coordinator.data[KEY_CAMERAS]
        refreshed_camera_ids = set()
        entities_to_add = []

        for camera in cameras:
            if not _is_acceptable_camera(camera):
                return
            camera_id = camera[KEY_ID]

            refreshed_camera_ids.add(camera_id)
            if camera_id in current_camera_ids:
                continue
            current_camera_ids.add(camera_id)

            surveillance_username = entry.data.get(
                CONF_USERNAME_SURVEILLANCE, DEFAULT_USERNAME_SURVEILLANCE
            )
            surveillance_password = entry.data.get(CONF_PASSWORD_SURVEILLANCE, "")

            entities_to_add.append(
                MotionEyeMjpegCamera(
                    entry.data[CONF_HOST],
                    entry.data[CONF_PORT],
                    surveillance_username,
                    surveillance_password,
                    camera,
                    entry_data[CONF_CLIENT],
                    coordinator,
                )
            )

        async_add_entities(entities_to_add)
        _remove_cameras(current_camera_ids - refreshed_camera_ids)

    _process_camera_entities()
    entry_data[CONF_ON_UNLOAD].append(
        coordinator.async_add_listener(_process_camera_entities)
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
        self._surveillance_username = username
        self._surveillance_password = password
        self._client = client
        self._camera_id = camera[KEY_ID]
        self._unique_id = get_motioneye_unique_id(
            host, port, self._camera_id, TYPE_MOTIONEYE_MJPEG_CAMERA
        )
        self._motion_detection_enabled = camera.get(KEY_MOTION_DETECTION, False)

        # motionEye cameras are always streaming. If streaming is stopped on the
        # motionEye side, the camera is automatically removed from HomeAssistant.
        self.is_streaming = True

        MjpegCamera.__init__(
            self,
            {
                CONF_VERIFY_SSL: False,
                **self._get_mjpeg_camera_properties_for_camera(camera),
            },
        )
        CoordinatorEntity.__init__(self, coordinator)

    def _get_mjpeg_camera_properties_for_camera(self, camera: Dict[str, Any]):
        """Convert a motionEye camera to MjpegCamera internal properties."""
        auth = None
        if camera[KEY_STREAMING_AUTH_MODE] in [
            HTTP_BASIC_AUTHENTICATION,
            HTTP_DIGEST_AUTHENTICATION,
        ]:
            auth = camera[KEY_STREAMING_AUTH_MODE]

        return {
            CONF_NAME: camera[KEY_NAME],
            CONF_USERNAME: self._surveillance_username if auth is not None else None,
            CONF_PASSWORD: self._surveillance_password if auth is not None else None,
            CONF_MJPEG_URL: self._client.get_camera_steam_url(camera),
            CONF_STILL_IMAGE_URL: self._client.get_camera_snapshot_url(camera),
            CONF_AUTHENTICATION: auth,
        }

    def _set_mjpeg_camera_state_for_camera(self, camera: Dict[str, Any]):
        """Set the internal state to match the given camera."""

        # Sets the state of the underlying (inherited) MjpegCamera based on the updated
        # MotionEye camera dictionary.
        properties = self._get_mjpeg_camera_properties_for_camera(camera)
        self._name = properties[CONF_NAME]
        self._username = properties[CONF_USERNAME]
        self._password = properties[CONF_PASSWORD]
        self._mjpeg_url = properties[CONF_MJPEG_URL]
        self._still_image_url = properties[CONF_STILL_IMAGE_URL]
        self._authentication = properties[CONF_AUTHENTICATION]

        if self._authentication == HTTP_BASIC_AUTHENTICATION:
            self._auth = aiohttp.BasicAuth(self._username, password=self._password)

    @property
    def unique_id(self) -> str:
        """Return a unique id for this instance."""
        return self._unique_id

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
            camera = get_camera_from_cameras(self._camera_id, self.coordinator.data)
            if _is_acceptable_camera(camera):
                self._set_mjpeg_camera_state_for_camera(camera)
                self._motion_detection_enabled = camera.get(KEY_MOTION_DETECTION, False)
                _LOGGER.error("============>MD %i" % self._motion_detection_enabled)
        CoordinatorEntity._handle_coordinator_update(self)

    @property
    def brand(self):
        """Return the camera brand."""
        return MOTIONEYE_MANUFACTURER

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self._motion_detection_enabled
