"""Support for OctoPrint binary camera."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from json import JSONDecodeError
import logging

import httpx
from propcache.api import cached_property
from pyoctoprintapi import OctoprintClient, WebcamSettings
from webrtc_models import RTCIceCandidateInit

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    WebRTCAnswer,
    WebRTCSendMessage,
)
from homeassistant.components.mjpeg import MjpegCamera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OctoprintDataUpdateCoordinator
from .const import DOMAIN, GET_IMAGE_TIMEOUT

_LOGGER = logging.getLogger(__name__)

#: Type alias for a callable that creates a camera from Octoprint camera information.
_OctoprintCameraConstructor = Callable[
    [WebcamSettings, OctoprintDataUpdateCoordinator, str, bool], Camera
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
        camera_ctor = OctoprintHlsCamera
    elif camera_info.stream_url.startswith(("webrtc://", "webrtcs://")):
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

    _attr_is_streaming = True

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


class _OctoprintCamera(CoordinatorEntity[OctoprintDataUpdateCoordinator], Camera):
    """Representation of an OctoPrint Camera Stream."""

    _attr_name = "OctoPrint Camera"
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_is_streaming = True

    def __init__(
        self,
        camera_settings: WebcamSettings,
        coordinator: OctoprintDataUpdateCoordinator,
        device_id: str,
        verify_ssl: bool,
    ) -> None:
        CoordinatorEntity.__init__(
            self,
            coordinator=coordinator,
        )
        Camera.__init__(self)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = device_id

        self._camera_settings = camera_settings
        self._verify_ssl = verify_ssl

        self._last_image: bytes | None = None
        self._last_update = datetime.min
        self._update_lock = asyncio.Lock()

    @cached_property
    def use_stream_for_stills(self) -> bool:
        """Use stream for stills if no snapshot URL is available."""
        return not self._camera_settings.internal_snapshot_url

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        "Fetch the camera image from the Octoprint URL."

        if not (url := self._camera_settings.internal_snapshot_url):
            return None

        # Lock to prevent concurrent calls to async_camera_image() from making concurrent requests to the snapshot URL,
        # and thus violating our _attr_frame_interval limit. When the first call releases the lock, other waiting calls
        # will (usually) just immediately return the cached _last_image from the first.
        async with self._update_lock:
            if (
                self._last_image is not None
                and self._last_update + timedelta(0, self._attr_frame_interval)
                > datetime.now()
            ):
                return self._last_image

            try:
                update_time = datetime.now()
                async_client = get_async_client(
                    self.hass,
                    verify_ssl=self._verify_ssl
                    and self._camera_settings.snapshot_ssl_validation_enabled,
                )
                response = await async_client.get(
                    url,
                    follow_redirects=True,
                    timeout=GET_IMAGE_TIMEOUT,
                )
                response.raise_for_status()
                self._last_image = response.content
                self._last_update = update_time

            except httpx.TimeoutException:
                _LOGGER.error("Timeout getting camera image from %s", self.name)
            except (httpx.RequestError, httpx.HTTPStatusError) as err:
                _LOGGER.error(
                    "Error getting new camera image from %s: %s", self.name, err
                )

            return self._last_image


class OctoprintHlsCamera(_OctoprintCamera):
    """Representation of an HLS OctoPrint Camera Stream."""

    async def stream_source(self) -> str:
        "Use the Octoprint HLS URL as the stream source."

        return self._camera_settings.stream_url


class OctoprintWebrtcCamera(_OctoprintCamera):
    """Representation of an OctoPrint WebRTC Camera Stream."""

    @cached_property
    def _offer_url(self) -> str:
        "The offer/answer signaling URL."

        url = self._camera_settings.stream_url

        # Transform "webrtc(s)://" to "http(s)://", like Octoprint does
        if url.startswith(("webrtc://", "webrtcs://")):
            url = f"http{url[6:]}"

        return url

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Handle an SDP offer via HTTP POST, like Octoprint does."""

        # POST the offer and get the answer in response. This is the signaling protocol the Octoprint front-end uses,
        # so if it works there it should work here too. (Like WHEP, but JSONified.)

        try:
            async_client = get_async_client(self.hass, verify_ssl=self._verify_ssl)
            response = await async_client.post(
                self._offer_url,
                follow_redirects=True,
                json={
                    "type": "offer",
                    "sdp": offer_sdp,
                },
            )
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as err:
            raise HomeAssistantError(
                f"Error during WebRTC signaling HTTP POST for {self.name}: {err}"
            ) from err

        try:
            response_json = response.json()
        except (UnicodeDecodeError, JSONDecodeError) as err:
            raise HomeAssistantError(
                f"Invalid answer response for {self.name}: {err}"
            ) from err

        if (
            response_json.get("type") != "answer"
            or (response_sdp := response_json.get("sdp")) is None
        ):
            raise HomeAssistantError(f"Invalid answer response for {self.name}")

        send_message(WebRTCAnswer(response_sdp))

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        "Ignore additional WebRTC candidates."
        # No mechanism to send additional candidates. Octoprint waits for all local candidates to be generated before
        # sending the offer, so that they are included there. That does not seem possible here. Just do the best we can.
        _LOGGER.debug("Ignoring WebRTC candidate for %s: %s", session_id, candidate)
