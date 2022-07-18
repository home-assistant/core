"""Support for IP Cameras."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from contextlib import closing

import aiohttp
from aiohttp import web
import async_timeout
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_web,
    async_get_clientsession,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MJPEG_URL, CONF_STILL_IMAGE_URL, DOMAIN, LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a MJPEG IP Camera based on a config entry."""
    async_add_entities(
        [
            MjpegCamera(
                name=entry.title,
                authentication=entry.options[CONF_AUTHENTICATION],
                username=entry.options.get(CONF_USERNAME),
                password=entry.options[CONF_PASSWORD],
                mjpeg_url=entry.options[CONF_MJPEG_URL],
                still_image_url=entry.options.get(CONF_STILL_IMAGE_URL),
                verify_ssl=entry.options[CONF_VERIFY_SSL],
                unique_id=entry.entry_id,
                device_info=DeviceInfo(
                    name=entry.title,
                    identifiers={(DOMAIN, entry.entry_id)},
                ),
            )
        ]
    )


def extract_image_from_mjpeg(stream: Iterable[bytes]) -> bytes | None:
    """Take in a MJPEG stream object, return the jpg from it."""
    data = b""

    for chunk in stream:
        data += chunk
        jpg_end = data.find(b"\xff\xd9")

        if jpg_end == -1:
            continue

        jpg_start = data.find(b"\xff\xd8")

        if jpg_start == -1:
            continue

        return data[jpg_start : jpg_end + 2]

    return None


class MjpegCamera(Camera):
    """An implementation of an IP camera that is reachable over a URL."""

    def __init__(
        self,
        *,
        name: str | None = None,
        mjpeg_url: str,
        still_image_url: str | None,
        authentication: str | None = None,
        username: str | None = None,
        password: str = "",
        verify_ssl: bool = True,
        unique_id: str | None = None,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Initialize a MJPEG camera."""
        super().__init__()
        self._attr_name = name
        self._authentication = authentication
        self._username = username
        self._password = password
        self._mjpeg_url = mjpeg_url
        self._still_image_url = still_image_url

        self._auth = None
        if (
            self._username
            and self._password
            and self._authentication == HTTP_BASIC_AUTHENTICATION
        ):
            self._auth = aiohttp.BasicAuth(self._username, password=self._password)
        self._verify_ssl = verify_ssl

        if unique_id is not None:
            self._attr_unique_id = unique_id
        if device_info is not None:
            self._attr_device_info = device_info

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        # DigestAuth is not supported
        if (
            self._authentication == HTTP_DIGEST_AUTHENTICATION
            or self._still_image_url is None
        ):
            image = await self.hass.async_add_executor_job(self.camera_image)
            return image

        websession = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
        try:
            async with async_timeout.timeout(10):
                response = await websession.get(self._still_image_url, auth=self._auth)

                image = await response.read()
                return image

        except asyncio.TimeoutError:
            LOGGER.error("Timeout getting camera image from %s", self.name)

        except aiohttp.ClientError as err:
            LOGGER.error("Error getting new camera image from %s: %s", self.name, err)

        return None

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        if self._username and self._password:
            if self._authentication == HTTP_DIGEST_AUTHENTICATION:
                auth: HTTPDigestAuth | HTTPBasicAuth = HTTPDigestAuth(
                    self._username, self._password
                )
            else:
                auth = HTTPBasicAuth(self._username, self._password)
            req = requests.get(
                self._mjpeg_url,
                auth=auth,
                stream=True,
                timeout=10,
                verify=self._verify_ssl,
            )
        else:
            req = requests.get(self._mjpeg_url, stream=True, timeout=10)

        with closing(req) as response:
            return extract_image_from_mjpeg(response.iter_content(102400))

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse | None:
        """Generate an HTTP MJPEG stream from the camera."""
        # aiohttp don't support DigestAuth -> Fallback
        if self._authentication == HTTP_DIGEST_AUTHENTICATION:
            return await super().handle_async_mjpeg_stream(request)

        # connect to stream
        websession = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
        stream_coro = websession.get(self._mjpeg_url, auth=self._auth)

        return await async_aiohttp_proxy_web(self.hass, request, stream_coro)
