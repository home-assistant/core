"""The Brands integration."""

from __future__ import annotations

from collections import deque
from http import HTTPStatus
import logging
from pathlib import Path
from random import SystemRandom
import time
from typing import Any, Final

from aiohttp import ClientError, hdrs, web
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.core import HomeAssistant, callback, valid_domain
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_custom_components

from .const import (
    ALLOWED_IMAGES,
    BRANDS_CDN_URL,
    CACHE_TTL,
    CATEGORY_RE,
    CDN_TIMEOUT,
    DOMAIN,
    HARDWARE_IMAGE_RE,
    IMAGE_FALLBACKS,
    PLACEHOLDER,
    TOKEN_CHANGE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)
_RND: Final = SystemRandom()

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Brands integration."""
    access_tokens: deque[str] = deque([], 2)
    access_tokens.append(hex(_RND.getrandbits(256))[2:])
    hass.data[DOMAIN] = access_tokens

    @callback
    def _rotate_token(_now: Any) -> None:
        """Rotate the access token."""
        access_tokens.append(hex(_RND.getrandbits(256))[2:])

    async_track_time_interval(hass, _rotate_token, TOKEN_CHANGE_INTERVAL)

    hass.http.register_view(BrandsIntegrationView(hass))
    hass.http.register_view(BrandsHardwareView(hass))
    websocket_api.async_register_command(hass, ws_access_token)
    return True


@callback
@websocket_api.websocket_command({vol.Required("type"): "brands/access_token"})
def ws_access_token(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the current brands access token."""
    access_tokens: deque[str] = hass.data[DOMAIN]
    connection.send_result(msg["id"], {"token": access_tokens[-1]})


def _read_cached_file_with_marker(
    cache_path: Path,
) -> tuple[bytes | None, float] | None:
    """Read a cached file, distinguishing between content and 404 markers.

    Returns (content, mtime) where content is None for 404 markers (empty files).
    Returns None if the file does not exist at all.
    """
    if not cache_path.is_file():
        return None
    mtime = cache_path.stat().st_mtime
    data = cache_path.read_bytes()
    if not data:
        # Empty file is a 404 marker
        return (None, mtime)
    return (data, mtime)


def _write_cache_file(cache_path: Path, data: bytes) -> None:
    """Write data to cache file, creating directories as needed."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(data)


def _read_brand_file(brand_dir: Path, image: str) -> bytes | None:
    """Read a brand image, trying fallbacks in a single I/O pass."""
    for candidate in (image, *IMAGE_FALLBACKS.get(image, ())):
        file_path = brand_dir / candidate
        if file_path.is_file():
            return file_path.read_bytes()
    return None


class _BrandsBaseView(HomeAssistantView):
    """Base view for serving brand images."""

    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the view."""
        self._hass = hass
        self._cache_dir = Path(hass.config.cache_path(DOMAIN))

    def _authenticate(self, request: web.Request) -> None:
        """Authenticate the request using Bearer token or query token."""
        access_tokens: deque[str] = self._hass.data[DOMAIN]
        authenticated = (
            request[KEY_AUTHENTICATED] or request.query.get("token") in access_tokens
        )
        if not authenticated:
            if hdrs.AUTHORIZATION in request.headers:
                raise web.HTTPUnauthorized
            raise web.HTTPForbidden

    async def _serve_from_custom_integration(
        self,
        domain: str,
        image: str,
    ) -> web.Response | None:
        """Try to serve a brand image from a custom integration."""
        custom_components = await async_get_custom_components(self._hass)
        if (integration := custom_components.get(domain)) is None:
            return None
        if not integration.has_branding:
            return None

        brand_dir = Path(integration.file_path) / "brand"

        data = await self._hass.async_add_executor_job(
            _read_brand_file, brand_dir, image
        )
        if data is not None:
            return self._build_response(data)

        return None

    async def _serve_from_cache_or_cdn(
        self,
        cdn_path: str,
        cache_subpath: str,
        *,
        fallback_placeholder: bool = True,
    ) -> web.Response:
        """Serve from disk cache, fetching from CDN if needed."""
        cache_path = self._cache_dir / cache_subpath
        now = time.time()

        # Try disk cache
        result = await self._hass.async_add_executor_job(
            _read_cached_file_with_marker, cache_path
        )
        if result is not None:
            data, mtime = result
            # Schedule background refresh if stale
            if now - mtime > CACHE_TTL:
                self._hass.async_create_background_task(
                    self._fetch_and_cache(cdn_path, cache_path),
                    f"brands_refresh_{cache_subpath}",
                )
        else:
            # Cache miss - fetch from CDN
            data = await self._fetch_and_cache(cdn_path, cache_path)

        if data is None:
            if fallback_placeholder:
                return await self._serve_placeholder(
                    image=cache_subpath.rsplit("/", 1)[-1]
                )
            return web.Response(status=HTTPStatus.NOT_FOUND)
        return self._build_response(data)

    async def _fetch_and_cache(
        self,
        cdn_path: str,
        cache_path: Path,
    ) -> bytes | None:
        """Fetch from CDN and write to cache. Returns data or None on 404."""
        url = f"{BRANDS_CDN_URL}/{cdn_path}"
        session = async_get_clientsession(self._hass)
        try:
            resp = await session.get(url, timeout=CDN_TIMEOUT)
        except ClientError, TimeoutError:
            _LOGGER.debug("Failed to fetch brand from CDN: %s", cdn_path)
            return None

        if resp.status == HTTPStatus.NOT_FOUND:
            # Cache the 404 as empty file
            await self._hass.async_add_executor_job(_write_cache_file, cache_path, b"")
            return None

        if resp.status != HTTPStatus.OK:
            _LOGGER.debug("Unexpected CDN response %s for %s", resp.status, cdn_path)
            return None

        data = await resp.read()
        await self._hass.async_add_executor_job(_write_cache_file, cache_path, data)
        return data

    async def _serve_placeholder(self, image: str) -> web.Response:
        """Serve a placeholder image."""
        return await self._serve_from_cache_or_cdn(
            cdn_path=f"_/{PLACEHOLDER}/{image}",
            cache_subpath=f"integrations/{PLACEHOLDER}/{image}",
            fallback_placeholder=False,
        )

    @staticmethod
    def _build_response(data: bytes) -> web.Response:
        """Build a response with proper headers."""
        return web.Response(
            body=data,
            content_type="image/png",
        )


class BrandsIntegrationView(_BrandsBaseView):
    """Serve integration brand images."""

    name = "api:brands:integration"
    url = "/api/brands/integration/{domain}/{image}"

    async def get(
        self,
        request: web.Request,
        domain: str,
        image: str,
    ) -> web.Response:
        """Handle GET request for an integration brand image."""
        self._authenticate(request)

        if not valid_domain(domain) or image not in ALLOWED_IMAGES:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        use_placeholder = request.query.get("placeholder") != "no"

        # 1. Try custom integration local files
        if (
            response := await self._serve_from_custom_integration(domain, image)
        ) is not None:
            return response

        # 2. Try cache / CDN (always use direct path for proper 404 caching)
        return await self._serve_from_cache_or_cdn(
            cdn_path=f"brands/{domain}/{image}",
            cache_subpath=f"integrations/{domain}/{image}",
            fallback_placeholder=use_placeholder,
        )


class BrandsHardwareView(_BrandsBaseView):
    """Serve hardware brand images."""

    name = "api:brands:hardware"
    url = "/api/brands/hardware/{category}/{image:.+}"

    async def get(
        self,
        request: web.Request,
        category: str,
        image: str,
    ) -> web.Response:
        """Handle GET request for a hardware brand image."""
        self._authenticate(request)

        if not CATEGORY_RE.match(category):
            return web.Response(status=HTTPStatus.NOT_FOUND)
        # Hardware images have dynamic names like "manufacturer_model.png"
        # Validate it ends with .png and contains only safe characters
        if not HARDWARE_IMAGE_RE.match(image):
            return web.Response(status=HTTPStatus.NOT_FOUND)

        cache_subpath = f"hardware/{category}/{image}"

        return await self._serve_from_cache_or_cdn(
            cdn_path=cache_subpath,
            cache_subpath=cache_subpath,
        )
