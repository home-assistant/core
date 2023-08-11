"""Support for IP Cameras."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress

import aiohttp
from aiohttp import web
import async_timeout
import httpx
from yarl import URL

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_MJPEG_URL, CONF_STILL_IMAGE_URL, DOMAIN, LOGGER

TIMEOUT = 10
BUFFER_SIZE = 102400


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


async def async_extract_image_from_mjpeg(stream: AsyncIterator[bytes]) -> bytes | None:
    """Take in a MJPEG stream object, return the jpg from it."""
    data = b""

    async for chunk in stream:
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

    async def stream_source(self) -> str:
        """Return the stream source."""
        url = URL(self._mjpeg_url)
        if self._username:
            url = url.with_user(self._username)
        if self._password:
            url = url.with_password(self._password)
        return str(url)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        # DigestAuth is not supported
        if (
            self._authentication == HTTP_DIGEST_AUTHENTICATION
            or self._still_image_url is None
        ):
            return await self._async_digest_camera_image()

        websession = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
        try:
            async with async_timeout.timeout(TIMEOUT):
                response = await websession.get(self._still_image_url, auth=self._auth)

                image = await response.read()
                return image

        except asyncio.TimeoutError:
            LOGGER.error("Timeout getting camera image from %s", self.name)

        except aiohttp.ClientError as err:
            LOGGER.error("Error getting new camera image from %s: %s", self.name, err)

        return None

    def _get_digest_auth(self) -> httpx.DigestAuth:
        """Return a DigestAuth object."""
        username = "" if self._username is None else self._username
        return httpx.DigestAuth(username, self._password)

    async def _async_digest_camera_image(self) -> bytes | None:
        """Return a still image response from the camera using digest authentication."""
        client = get_async_client(self.hass, verify_ssl=self._verify_ssl)
        auth = self._get_digest_auth()
        try:
            if self._still_image_url:
                # Fallback to MJPEG stream if still image URL is not available
                with suppress(asyncio.TimeoutError, httpx.HTTPError):
                    return (
                        await client.get(
                            self._still_image_url, auth=auth, timeout=TIMEOUT
                        )
                    ).content

            async with client.stream(
                "get", self._mjpeg_url, auth=auth, timeout=TIMEOUT
            ) as stream:
                return await async_extract_image_from_mjpeg(
                    stream.aiter_bytes(BUFFER_SIZE)
                )

        except asyncio.TimeoutError:
            LOGGER.error("Timeout getting camera image from %s", self.name)

        except httpx.HTTPError as err:
            LOGGER.error("Error getting new camera image from %s: %s", self.name, err)

        return None

    async def _handle_async_mjpeg_digest_stream(
        self, request: web.Request
    ) -> web.StreamResponse | None:
        """Generate an HTTP MJPEG stream from the camera using digest authentication."""
        async with get_async_client(self.hass, verify_ssl=self._verify_ssl).stream(
            "get", self._mjpeg_url, auth=self._get_digest_auth(), timeout=TIMEOUT
        ) as stream:
            response = web.StreamResponse(headers=stream.headers)
            await response.prepare(request)
            # Stream until we are done or client disconnects
            with suppress(asyncio.TimeoutError, httpx.HTTPError):
                async for chunk in stream.aiter_bytes(BUFFER_SIZE):
                    if not self.hass.is_running:
                        break
                    async with async_timeout.timeout(TIMEOUT):
                        await response.write(chunk)
        return response

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse | None:
        """Generate an HTTP MJPEG stream from the camera."""
        # aiohttp don't support DigestAuth so we use httpx
        if self._authentication == HTTP_DIGEST_AUTHENTICATION:
            return await self._handle_async_mjpeg_digest_stream(request)

        # connect to stream
        websession = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
        stream_coro = websession.get(self._mjpeg_url, auth=self._auth)

        return await async_aiohttp_proxy_web(self.hass, request, stream_coro)
