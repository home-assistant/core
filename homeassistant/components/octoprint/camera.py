"""Support for OctoPrint binary camera."""
from __future__ import annotations

from collections.abc import Callable
from json import JSONDecodeError

import httpx
from pyoctoprintapi import OctoprintClient, WebcamSettings

from homeassistant.components.camera import DEFAULT_CONTENT_TYPE, Camera, StreamType
from homeassistant.components.generic.camera import (
    CONF_CONTENT_TYPE,
    CONF_FRAMERATE,
    CONF_LIMIT_REFETCH_TO_URL_CHANGE,
    CONF_STILL_IMAGE_URL,
    CONF_STREAM_SOURCE,
    GenericCamera,
)
from homeassistant.components.mjpeg.camera import MjpegCamera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OctoprintDataUpdateCoordinator

#: Type alias for a callable that creates a camera from Octoprint camera information.
_OctoprintCameraConstructor = Callable[
    [WebcamSettings, OctoprintDataUpdateCoordinator, str, bool], Camera
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the available OctoPrint camera."""
    coordinator: OctoprintDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]
    client: OctoprintClient = hass.data[DOMAIN][config_entry.entry_id]["client"]
    device_id = config_entry.unique_id

    assert device_id is not None

    camera_info = await client.get_webcam_info()
    verify_ssl = config_entry.data[CONF_VERIFY_SSL]

    if not camera_info or not camera_info.enabled:
        return

    # Choose correct implementation based on the stream type, using the same logic the Octoprint front-end does
    camera_ctor: _OctoprintCameraConstructor
    if camera_info.stream_url.endswith(".m3u8"):
        camera_ctor = OctoprintGenericCamera  # HLS
    elif camera_info.stream_url.startswith(
        "webrtc://"
    ) or camera_info.stream_url.startswith("webrtcs://"):
        camera_ctor = OctoprintWebrtcCamera
    else:
        camera_ctor = OctoprintMjpegCamera

    async_add_entities(
        [
            camera_ctor(
                camera_info,
                coordinator,
                device_id,
                verify_ssl,
            )
        ]
    )


class OctoprintMjpegCamera(
    CoordinatorEntity[OctoprintDataUpdateCoordinator], MjpegCamera
):
    """Representation of an OctoPrint MJPEG Camera Stream."""

    def __init__(
        self,
        camera_settings: WebcamSettings,
        coordinator: OctoprintDataUpdateCoordinator,
        device_id: str,
        verify_ssl: bool,
    ) -> None:
        """Initialize as a subclass of MjpegCamera."""
        CoordinatorEntity.__init__(
            self,
            coordinator=coordinator,
        )
        MjpegCamera.__init__(
            self,
            device_info=coordinator.device_info,
            mjpeg_url=camera_settings.stream_url,
            name="OctoPrint Camera",
            still_image_url=camera_settings.external_snapshot_url,
            unique_id=device_id,
            verify_ssl=verify_ssl,
        )


class OctoprintGenericCamera(
    CoordinatorEntity[OctoprintDataUpdateCoordinator], GenericCamera
):
    """Representation of a generic OctoPrint Camera Stream."""

    def __init__(
        self,
        camera_settings: WebcamSettings,
        coordinator: OctoprintDataUpdateCoordinator,
        device_id: str,
        verify_ssl: bool,
    ) -> None:
        """Initialize as a subclass of GenericCamera."""

        CoordinatorEntity.__init__(
            self,
            coordinator=coordinator,
        )
        GenericCamera.__init__(
            self,
            hass=coordinator.hass,
            device_info={
                CONF_STREAM_SOURCE: camera_settings.stream_url,
                CONF_STILL_IMAGE_URL: camera_settings.internal_snapshot_url,
                CONF_VERIFY_SSL: verify_ssl,
                CONF_CONTENT_TYPE: DEFAULT_CONTENT_TYPE,
                CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
                CONF_FRAMERATE: 2,
            },
            identifier=device_id,
            title="OctoPrint Camera",
        )


class OctoprintWebrtcCamera(OctoprintGenericCamera):
    """Representation of an OctoPrint WebRTC Camera Stream."""

    _attr_frontend_stream_type = StreamType.WEB_RTC

    async def async_handle_web_rtc_offer(self, offer_sdp: str) -> str | None:
        """Handle an SDP offer via HTTP POST, like Octoprint does."""

        url = await self.stream_source()
        if url is None:
            return None

        # POST the offer and get the answer in response. This is the signaling protocol Octoprint uses, so if it works
        # there it should work here too.

        # Transform "webrtc(s)://" to "http(s)://"
        if url.startswith("webrtc://") or url.startswith("webrtcs://"):
            url = f"http{url[6:]}"

        try:
            async_client = get_async_client(self.hass, verify_ssl=self.verify_ssl)
            response = await async_client.post(
                url,
                auth=self._auth or httpx.USE_CLIENT_DEFAULT,
                follow_redirects=True,
                json={
                    "type": "offer",
                    "sdp": offer_sdp,
                },
            )
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as err:
            raise HomeAssistantError(
                f"Error during WebRTC signaling HTTP POST for {self._name}: {err}"
            ) from err

        try:
            return response.json()["sdp"]
        except (UnicodeDecodeError, JSONDecodeError, KeyError) as err:
            raise HomeAssistantError(
                f"Error decoding SDP answer for {self._name}: {err}"
            ) from err
