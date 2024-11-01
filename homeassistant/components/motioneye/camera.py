"""The motionEye integration."""

from __future__ import annotations

from contextlib import suppress
from types import MappingProxyType
from typing import Any

import aiohttp
from jinja2 import Template
from motioneye_client.client import MotionEyeClient, MotionEyeClientURLParseError
from motioneye_client.const import (
    DEFAULT_SURVEILLANCE_USERNAME,
    KEY_ACTION_SNAPSHOT,
    KEY_MOTION_DETECTION,
    KEY_STREAMING_AUTH_MODE,
    KEY_TEXT_OVERLAY_CAMERA_NAME,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT,
    KEY_TEXT_OVERLAY_DISABLED,
    KEY_TEXT_OVERLAY_LEFT,
    KEY_TEXT_OVERLAY_RIGHT,
    KEY_TEXT_OVERLAY_TIMESTAMP,
)
import voluptuous as vol

from homeassistant.components.mjpeg import (
    CONF_MJPEG_URL,
    CONF_STILL_IMAGE_URL,
    MjpegCamera,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import get_camera_from_cameras, is_acceptable_camera, listen_for_new_cameras
from .const import (
    CONF_ACTION,
    CONF_CLIENT,
    CONF_COORDINATOR,
    CONF_STREAM_URL_TEMPLATE,
    CONF_SURVEILLANCE_PASSWORD,
    CONF_SURVEILLANCE_USERNAME,
    DOMAIN,
    MOTIONEYE_MANUFACTURER,
    SERVICE_ACTION,
    SERVICE_SET_TEXT_OVERLAY,
    SERVICE_SNAPSHOT,
    TYPE_MOTIONEYE_MJPEG_CAMERA,
)
from .entity import MotionEyeEntity

PLATFORMS = [Platform.CAMERA]

SCHEMA_TEXT_OVERLAY = vol.In(
    [
        KEY_TEXT_OVERLAY_DISABLED,
        KEY_TEXT_OVERLAY_TIMESTAMP,
        KEY_TEXT_OVERLAY_CUSTOM_TEXT,
        KEY_TEXT_OVERLAY_CAMERA_NAME,
    ]
)
SCHEMA_SERVICE_SET_TEXT = vol.Schema(
    vol.All(
        cv.make_entity_service_schema(
            {
                vol.Optional(KEY_TEXT_OVERLAY_LEFT): SCHEMA_TEXT_OVERLAY,
                vol.Optional(KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT): cv.string,
                vol.Optional(KEY_TEXT_OVERLAY_RIGHT): SCHEMA_TEXT_OVERLAY,
                vol.Optional(KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT): cv.string,
            },
        ),
        cv.has_at_least_one_key(
            KEY_TEXT_OVERLAY_LEFT,
            KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT,
            KEY_TEXT_OVERLAY_RIGHT,
            KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT,
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up motionEye from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]

    @callback
    def camera_add(camera: dict[str, Any]) -> None:
        """Add a new motionEye camera."""
        async_add_entities(
            [
                MotionEyeMjpegCamera(
                    entry.entry_id,
                    entry.data.get(
                        CONF_SURVEILLANCE_USERNAME, DEFAULT_SURVEILLANCE_USERNAME
                    ),
                    entry.data.get(CONF_SURVEILLANCE_PASSWORD, ""),
                    camera,
                    entry_data[CONF_CLIENT],
                    entry_data[CONF_COORDINATOR],
                    entry.options,
                )
            ]
        )

    listen_for_new_cameras(hass, entry, camera_add)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_TEXT_OVERLAY,
        SCHEMA_SERVICE_SET_TEXT,
        "async_set_text_overlay",
    )
    platform.async_register_entity_service(
        SERVICE_ACTION,
        {vol.Required(CONF_ACTION): cv.string},
        "async_request_action",
    )
    platform.async_register_entity_service(
        SERVICE_SNAPSHOT,
        None,
        "async_request_snapshot",
    )


class MotionEyeMjpegCamera(MotionEyeEntity, MjpegCamera):
    """motionEye mjpeg camera."""

    _attr_brand = MOTIONEYE_MANUFACTURER
    # motionEye cameras are always streaming or unavailable.
    _attr_is_streaming = True

    def __init__(
        self,
        config_entry_id: str,
        username: str,
        password: str,
        camera: dict[str, Any],
        client: MotionEyeClient,
        coordinator: DataUpdateCoordinator,
        options: MappingProxyType[str, str],
    ) -> None:
        """Initialize a MJPEG camera."""
        self._surveillance_username = username
        self._surveillance_password = password
        self._motion_detection_enabled: bool = camera.get(KEY_MOTION_DETECTION, False)

        MotionEyeEntity.__init__(
            self,
            config_entry_id,
            TYPE_MOTIONEYE_MJPEG_CAMERA,
            camera,
            client,
            coordinator,
            options,
        )
        MjpegCamera.__init__(
            self,
            verify_ssl=False,
            **self._get_mjpeg_camera_properties_for_camera(camera),
        )

    @callback
    def _get_mjpeg_camera_properties_for_camera(
        self, camera: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert a motionEye camera to MjpegCamera internal properties."""
        auth = None
        if camera.get(KEY_STREAMING_AUTH_MODE) in (
            HTTP_BASIC_AUTHENTICATION,
            HTTP_DIGEST_AUTHENTICATION,
        ):
            auth = camera[KEY_STREAMING_AUTH_MODE]

        streaming_template = self._options.get(CONF_STREAM_URL_TEMPLATE, "").strip()
        streaming_url = None

        if streaming_template:
            # Note: Can't use homeassistant.helpers.template as it requires hass
            # which is not available during entity construction.
            streaming_url = Template(streaming_template).render(**camera)
        else:
            with suppress(MotionEyeClientURLParseError):
                streaming_url = self._client.get_camera_stream_url(camera)

        return {
            CONF_NAME: None,
            CONF_USERNAME: self._surveillance_username if auth is not None else None,
            CONF_PASSWORD: self._surveillance_password if auth is not None else "",
            CONF_MJPEG_URL: streaming_url or "",
            CONF_STILL_IMAGE_URL: self._client.get_camera_snapshot_url(camera),
            CONF_AUTHENTICATION: auth,
        }

    @callback
    def _set_mjpeg_camera_state_for_camera(self, camera: dict[str, Any]) -> None:
        """Set the internal state to match the given camera."""

        # Sets the state of the underlying (inherited) MjpegCamera based on the updated
        # MotionEye camera dictionary.
        properties = self._get_mjpeg_camera_properties_for_camera(camera)
        self._username = properties[CONF_USERNAME]
        self._password = properties[CONF_PASSWORD]
        self._mjpeg_url = properties[CONF_MJPEG_URL]
        self._still_image_url = properties[CONF_STILL_IMAGE_URL]
        self._authentication = properties[CONF_AUTHENTICATION]

        if (
            self._authentication == HTTP_BASIC_AUTHENTICATION
            and self._username is not None
        ):
            self._auth = aiohttp.BasicAuth(self._username, password=self._password)

    def _is_acceptable_streaming_camera(self) -> bool:
        """Determine if a camera is streaming/usable."""
        return is_acceptable_camera(
            self._camera
        ) and MotionEyeClient.is_camera_streaming(self._camera)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._is_acceptable_streaming_camera()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._camera = get_camera_from_cameras(self._camera_id, self.coordinator.data)
        if self._camera and self._is_acceptable_streaming_camera():
            self._set_mjpeg_camera_state_for_camera(self._camera)
            self._motion_detection_enabled = self._camera.get(
                KEY_MOTION_DETECTION, False
            )
        super()._handle_coordinator_update()

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return self._motion_detection_enabled

    async def async_set_text_overlay(
        self,
        left_text: str | None = None,
        right_text: str | None = None,
        custom_left_text: str | None = None,
        custom_right_text: str | None = None,
    ) -> None:
        """Set text overlay for a camera."""
        # Fetch the very latest camera config to reduce the risk of updating with a
        # stale configuration.
        camera = await self._client.async_get_camera(self._camera_id)
        if not camera:
            return
        if left_text is not None:
            camera[KEY_TEXT_OVERLAY_LEFT] = left_text
        if right_text is not None:
            camera[KEY_TEXT_OVERLAY_RIGHT] = right_text
        if custom_left_text is not None:
            camera[KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT] = custom_left_text.encode(
                "unicode_escape"
            ).decode("UTF-8")
        if custom_right_text is not None:
            camera[KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT] = custom_right_text.encode(
                "unicode_escape"
            ).decode("UTF-8")
        await self._client.async_set_camera(self._camera_id, camera)

    async def async_request_action(self, action: str) -> None:
        """Call a motionEye action on a camera."""
        await self._client.async_action(self._camera_id, action)

    async def async_request_snapshot(self) -> None:
        """Request a motionEye snapshot be saved."""
        await self.async_request_action(KEY_ACTION_SNAPSHOT)
