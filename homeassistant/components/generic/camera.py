"""Support for IP Cameras."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timedelta
import logging
from typing import Any

import httpx
import voluptuous as vol
import yarl

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.stream import (
    CONF_RTSP_TRANSPORT,
    CONF_USE_WALLCLOCK_AS_TIMESTAMPS,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.template import Template

from . import DOMAIN
from .const import (
    CONF_CONTENT_TYPE,
    CONF_FRAMERATE,
    CONF_LIMIT_REFETCH_TO_URL_CHANGE,
    CONF_STILL_IMAGE_URL,
    CONF_STREAM_SOURCE,
    GET_IMAGE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a generic IP Camera."""

    async_add_entities(
        [GenericCamera(hass, entry.options, entry.entry_id, entry.title)]
    )


def generate_auth(device_info: Mapping[str, Any]) -> httpx.Auth | None:
    """Generate httpx.Auth object from credentials."""
    username: str | None = device_info.get(CONF_USERNAME)
    password: str | None = device_info.get(CONF_PASSWORD)
    authentication = device_info.get(CONF_AUTHENTICATION)
    if username and password:
        if authentication == HTTP_DIGEST_AUTHENTICATION:
            return httpx.DigestAuth(username=username, password=password)
        return httpx.BasicAuth(username=username, password=password)
    return None


class GenericCamera(Camera):
    """A generic implementation of an IP camera."""

    _last_image: bytes | None
    _last_update: datetime
    _update_lock: asyncio.Lock

    def __init__(
        self,
        hass: HomeAssistant,
        device_info: Mapping[str, Any],
        identifier: str,
        title: str,
    ) -> None:
        """Initialize a generic camera."""
        super().__init__()
        self.hass = hass
        self._attr_unique_id = identifier
        self._authentication = device_info.get(CONF_AUTHENTICATION)
        self._username = device_info.get(CONF_USERNAME)
        self._password = device_info.get(CONF_PASSWORD)
        self._name = device_info.get(CONF_NAME, title)
        self._still_image_url = device_info.get(CONF_STILL_IMAGE_URL)
        if self._still_image_url:
            self._still_image_url = Template(self._still_image_url, hass)
        self._stream_source = device_info.get(CONF_STREAM_SOURCE)
        if self._stream_source:
            self._stream_source = Template(self._stream_source, hass)
            self._attr_supported_features = CameraEntityFeature.STREAM
        self._limit_refetch = device_info.get(CONF_LIMIT_REFETCH_TO_URL_CHANGE, False)
        self._attr_frame_interval = 1 / device_info[CONF_FRAMERATE]
        self.content_type = device_info[CONF_CONTENT_TYPE]
        self.verify_ssl = device_info[CONF_VERIFY_SSL]
        if device_info.get(CONF_RTSP_TRANSPORT):
            self.stream_options[CONF_RTSP_TRANSPORT] = device_info[CONF_RTSP_TRANSPORT]
        self._auth = generate_auth(device_info)
        if device_info.get(CONF_USE_WALLCLOCK_AS_TIMESTAMPS):
            self.stream_options[CONF_USE_WALLCLOCK_AS_TIMESTAMPS] = True

        self._last_url = None
        self._last_image = None
        self._last_update = datetime.min
        self._update_lock = asyncio.Lock()

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer="Generic",
        )

    @property
    def use_stream_for_stills(self) -> bool:
        """Whether or not to use stream to generate stills."""
        return not self._still_image_url

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        if not self._still_image_url:
            return None
        try:
            url = self._still_image_url.async_render(parse_result=False)
        except TemplateError as err:
            _LOGGER.error("Error parsing template %s: %s", self._still_image_url, err)
            return self._last_image

        try:
            vol.Schema(vol.Url())(url)
        except vol.Invalid as err:
            _LOGGER.warning("Invalid URL '%s': %s, returning last image", url, err)
            return self._last_image

        if url == self._last_url and self._limit_refetch:
            return self._last_image

        async with self._update_lock:
            if (
                self._last_image is not None
                and url == self._last_url
                and self._last_update + timedelta(0, self._attr_frame_interval)
                > datetime.now()
            ):
                return self._last_image

            try:
                update_time = datetime.now()
                async_client = get_async_client(self.hass, verify_ssl=self.verify_ssl)
                response = await async_client.get(
                    url,
                    auth=self._auth,
                    follow_redirects=True,
                    timeout=GET_IMAGE_TIMEOUT,
                )
                response.raise_for_status()
                self._last_image = response.content
                self._last_update = update_time

            except httpx.TimeoutException:
                _LOGGER.error("Timeout getting camera image from %s", self._name)
                return self._last_image
            except (httpx.RequestError, httpx.HTTPStatusError) as err:
                _LOGGER.error(
                    "Error getting new camera image from %s: %s", self._name, err
                )
                return self._last_image

            self._last_url = url
            return self._last_image

    @property
    def name(self) -> str:
        """Return the name of this device."""
        return self._name

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        if self._stream_source is None:
            return None

        try:
            stream_url = self._stream_source.async_render(parse_result=False)
            url = yarl.URL(stream_url)
            if (
                not url.user
                and not url.password
                and self._username
                and self._password
                and url.is_absolute()
            ):
                url = url.with_user(self._username).with_password(self._password)
            return str(url)
        except TemplateError as err:
            _LOGGER.error("Error parsing template %s: %s", self._stream_source, err)
            return None
