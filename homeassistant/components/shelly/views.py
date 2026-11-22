"""Shelly HTTP views."""

from http import HTTPStatus
import re

from aiohttp import ClientError, ClientTimeout, web
from yarl import URL

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER
from .coordinator import ShellyConfigEntry
from .utils import get_device_url, get_storage_coordinator

STORAGE_PREFIX = "/storage/"
CHUNK_SIZE = 65536
SAFE_SEGMENT = re.compile(r"[A-Za-z0-9_.-]+")
FORWARD_REQUEST_HEADERS = ("Range", "If-Range", "If-None-Match")
FORWARD_RESPONSE_HEADERS = (
    "Content-Type",
    "Content-Length",
    "Content-Range",
    "Accept-Ranges",
    "ETag",
    "Cache-Control",
)
# No total limit, recordings can take long to stream.
UPSTREAM_TIMEOUT = ClientTimeout(total=None, sock_connect=10, sock_read=30)


@callback
def async_generate_storage_proxy_url(
    config_entry_id: str, device_url: str
) -> str | None:
    """Return the proxy URL for a device storage URL."""
    if not device_url.startswith(STORAGE_PREFIX):
        return None
    return (
        f"/api/shelly/storage/{config_entry_id}/"
        f"{device_url.removeprefix(STORAGE_PREFIX)}"
    )


class StorageProxyView(HomeAssistantView):
    """View to proxy media from Shelly device storage."""

    requires_auth = True
    url = "/api/shelly/storage/{config_entry_id}/{path:.+}"
    name = "api:shelly:storage"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the view."""
        self.hass = hass

    async def get(
        self, request: web.Request, config_entry_id: str, path: str
    ) -> web.StreamResponse:
        """Stream a file from device storage."""
        segments = path.split("/")
        if any(
            segment in (".", "..") or not SAFE_SEGMENT.fullmatch(segment)
            for segment in segments
        ):
            return web.Response(status=HTTPStatus.NOT_FOUND)

        entry: ShellyConfigEntry | None = self.hass.config_entries.async_get_entry(
            config_entry_id
        )
        if (
            entry is None
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
            or get_storage_coordinator(entry) is None
        ):
            return web.Response(status=HTTPStatus.NOT_FOUND)

        url = URL(get_device_url(entry.data)).joinpath("storage", *segments)
        # Content-Length is forwarded, so the body must not be decompressed.
        headers = {"Accept-Encoding": "identity"} | {
            name: value
            for name in FORWARD_REQUEST_HEADERS
            if (value := request.headers.get(name)) is not None
        }
        try:
            upstream = await async_get_clientsession(self.hass).get(
                url,
                headers=headers,
                allow_redirects=False,
                ssl=entry.data.get(CONF_VERIFY_SSL, False),
                timeout=UPSTREAM_TIMEOUT,
            )
        except (ClientError, TimeoutError) as err:
            LOGGER.debug(
                "Error fetching storage of %s: %s", entry.title, type(err).__name__
            )
            return web.Response(status=HTTPStatus.BAD_GATEWAY)

        async with upstream:
            response = web.StreamResponse(
                status=upstream.status,
                headers={
                    name: value
                    for name in FORWARD_RESPONSE_HEADERS
                    if (value := upstream.headers.get(name)) is not None
                },
            )
            await response.prepare(request)
            try:
                async for chunk in upstream.content.iter_chunked(CHUNK_SIZE):
                    await response.write(chunk)
            except (ClientError, TimeoutError) as err:
                LOGGER.debug(
                    "Error streaming storage of %s: %s",
                    entry.title,
                    type(err).__name__,
                )
                # Abort the connection so the client sees a truncated response.
                if request.transport is not None:
                    request.transport.close()
                return response

        await response.write_eof()
        return response
