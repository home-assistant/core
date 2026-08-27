"""HTTP views for the Map tiles integration."""

from functools import partial
import gzip
import hashlib
from http import HTTPStatus
import json
import logging
from typing import Final, override

from aiohttp import ClientError, hdrs, web

from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.json import json_bytes

from .cache import Asset, MapTilesCache
from .const import (
    ASSET_MAX_AGE,
    ASSET_TTL,
    ATTRIBUTION,
    BLOCKED_TILE_BYTES,
    BLOCKED_TILE_SHA256,
    DATA_ACCESS_TOKENS,
    FONTSTACK_RE,
    GLYPH_RANGE_RE,
    RASTER_MAX_ZOOM,
    RASTER_URL,
    SPRITE_NAME_RE,
    SPRITE_SET_RE,
    TILE_MAX_AGE,
    TILE_TTL,
    TILEJSON_MAX_AGE,
    TILEJSON_TTL,
    TILEJSON_URL,
    UPSTREAM_HEADERS,
    UPSTREAM_TIMEOUT,
    VECTOR_MAX_ZOOM,
    VECTOR_URL,
)

_LOGGER = logging.getLogger(__name__)

# Origin relative: an absolute URL built from the request would be wrong behind
# a reverse proxy that has not been told to forward the original host.
VECTOR_TILE_PATH = "/api/map_tiles/vector/{z}/{x}/{y}.mvt"

# int() on an arbitrarily long digit string is not free.
MAX_COORDINATE_DIGITS = 8

GZIP: Final = "gzip"


class _MapTilesView(HomeAssistantView):
    """Serve one class of map asset, from the cache or from upstream."""

    requires_auth = False

    content_type: str
    ttl: int
    max_age: int
    # Cached and served in the encoding upstream sent, so nothing is compressed
    # per request. PNG opts out: its digest has to match the bytes as made.
    store_encoded = True

    def __init__(self, hass: HomeAssistant, cache: MapTilesCache) -> None:
        """Initialize the view."""
        self._hass = hass
        self._cache = cache

    def _authenticate(self, request: web.Request) -> None:
        """Authenticate the request using Bearer token or query token."""
        access_tokens = self._hass.data[DATA_ACCESS_TOKENS]
        if request[KEY_AUTHENTICATED] or request.query.get("token") in access_tokens:
            return
        if hdrs.AUTHORIZATION in request.headers:
            # A real Bearer attempt, so let the ban middleware count it.
            raise web.HTTPUnauthorized
        # Most likely a query token that expired while a dashboard sat open, so
        # 403 rather than banning the user's own IP over it.
        raise web.HTTPForbidden

    async def _async_serve(
        self, request: web.Request, key: str, url: str
    ) -> web.Response:
        """Serve an asset from the cache, fetching it upstream on a miss."""
        asset = await self._cache.async_get(
            key, self.ttl, partial(self._async_fetch, url)
        )
        if asset is None:
            return web.Response(status=HTTPStatus.BAD_GATEWAY)

        body, encoding = asset.body, asset.encoding
        if encoding == GZIP and GZIP not in request.headers.get(
            hdrs.ACCEPT_ENCODING, ""
        ):
            body = await self._hass.async_add_executor_job(gzip.decompress, body)
            encoding = None

        headers = {
            hdrs.CACHE_CONTROL: f"public, max-age={self.max_age}",
            hdrs.VARY: hdrs.ACCEPT_ENCODING,
        }
        if encoding:
            headers[hdrs.CONTENT_ENCODING] = encoding

        return web.Response(body=body, content_type=self.content_type, headers=headers)

    async def _async_fetch(self, url: str) -> Asset | None:
        """Fetch url upstream, or None if it has nothing to give us."""
        session = async_get_clientsession(self._hass)
        try:
            response = await session.get(
                url,
                headers=UPSTREAM_HEADERS,
                timeout=UPSTREAM_TIMEOUT,
                auto_decompress=not self.store_encoded,
            )
            if response.status >= HTTPStatus.BAD_REQUEST:
                _LOGGER.debug("Upstream %s returned %s", url, response.status)
                return None
            # An empty body is a legitimate answer: a vector tile with nothing
            # in it comes back as a short 200, not a 204 or a 404.
            body = await response.read()
        except (ClientError, TimeoutError) as err:
            _LOGGER.debug("Upstream %s failed: %s", url, err)
            return None

        if not self.store_encoded:
            # The session decompressed it, so the upstream `Content-Encoding`
            # no longer describes these bytes and passing it on breaks decoding.
            return Asset(body, None)
        return Asset(body, response.headers.get(hdrs.CONTENT_ENCODING))


class _MapTilesTileView(_MapTilesView):
    """Serve map tiles."""

    ttl = TILE_TTL
    max_age = TILE_MAX_AGE
    max_zoom: int
    upstream: str
    key_template: str

    async def get(
        self, request: web.Request, z: str, x: str, y: str
    ) -> web.StreamResponse:
        """Handle a GET request for a tile."""
        self._authenticate(request)

        if any(len(part) > MAX_COORDINATE_DIGITS for part in (z, x, y)):
            return web.Response(status=HTTPStatus.NOT_FOUND)

        zoom, column, row = int(z), int(x), int(y)
        if zoom > self.max_zoom or column >= 2**zoom or row >= 2**zoom:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        coordinates = {"z": zoom, "x": column, "y": row}
        return await self._async_serve(
            request,
            self.key_template.format(**coordinates),
            self.upstream.format(**coordinates),
        )


class MapTilesVectorView(_MapTilesTileView):
    """Serve vector tiles."""

    name = "api:map_tiles:vector"
    url = "/api/map_tiles/vector/{z:[0-9]+}/{x:[0-9]+}/{y:[0-9]+}.mvt"
    content_type = "application/vnd.mapbox-vector-tile"
    max_zoom = VECTOR_MAX_ZOOM
    upstream = f"{VECTOR_URL}/shortbread_v1/{{z}}/{{x}}/{{y}}.mvt"
    key_template = "vector/{z}/{x}/{y}.mvt"


class MapTilesRasterView(_MapTilesTileView):
    """Serve raster tiles, for devices that cannot render vector ones."""

    name = "api:map_tiles:raster"
    url = "/api/map_tiles/raster/{z:[0-9]+}/{x:[0-9]+}/{y:[0-9]+}.png"
    content_type = "image/png"
    store_encoded = False
    max_zoom = RASTER_MAX_ZOOM
    upstream = f"{RASTER_URL}/{{z}}/{{x}}/{{y}}.png"
    key_template = "raster/{z}/{x}/{y}.png"

    @override
    async def _async_fetch(self, url: str) -> Asset | None:
        """Fetch a raster tile, rejecting the one that means we were blocked."""
        if (asset := await super()._async_fetch(url)) is None:
            return None

        # Caching it would serve "Access blocked" to the household for a week.
        # The User-Agent should make this unreachable, hence logged not retried.
        if (
            len(asset.body) == BLOCKED_TILE_BYTES
            and hashlib.sha256(asset.body).hexdigest() == BLOCKED_TILE_SHA256
        ):
            _LOGGER.error(
                "OpenStreetMap blocked a raster tile request, which means Home"
                " Assistant is no longer identifying itself the way their tile"
                " usage policy requires. Please report this"
            )
            return None

        return asset


class MapTilesGlyphsView(_MapTilesView):
    """Serve the SDF glyphs the map labels are drawn from."""

    name = "api:map_tiles:glyphs"
    url = "/api/map_tiles/fonts/{fontstack}/{glyph_range}"
    content_type = "application/x-protobuf"
    ttl = ASSET_TTL
    max_age = ASSET_MAX_AGE

    async def get(
        self, request: web.Request, fontstack: str, glyph_range: str
    ) -> web.StreamResponse:
        """Handle a GET request for a glyph range."""
        self._authenticate(request)

        if not FONTSTACK_RE.match(fontstack) or not GLYPH_RANGE_RE.match(glyph_range):
            return web.Response(status=HTTPStatus.NOT_FOUND)

        return await self._async_serve(
            request,
            f"fonts/{fontstack}/{glyph_range}",
            f"{VECTOR_URL}/styles/shortbread/fonts/{fontstack}/{glyph_range}",
        )


class _MapTilesSpritesView(_MapTilesView):
    """Serve the icon sprites the map symbols come from."""

    ttl = ASSET_TTL
    max_age = ASSET_MAX_AGE
    extension: str

    async def get(
        self, request: web.Request, sprite_set: str, name: str
    ) -> web.StreamResponse:
        """Handle a GET request for a sprite set."""
        self._authenticate(request)

        if not SPRITE_SET_RE.match(sprite_set) or not SPRITE_NAME_RE.match(name):
            return web.Response(status=HTTPStatus.NOT_FOUND)

        path = f"sprites/{sprite_set}/{name}{self.extension}"
        return await self._async_serve(
            request, path, f"{VECTOR_URL}/styles/shortbread/{path}"
        )


class MapTilesSpriteIndexView(_MapTilesSpritesView):
    """Serve the sprite index."""

    name = "api:map_tiles:sprite_index"
    url = "/api/map_tiles/sprites/{sprite_set}/{name}.json"
    content_type = "application/json"
    extension = ".json"


class MapTilesSpriteSheetView(_MapTilesSpritesView):
    """Serve the sprite sheet."""

    name = "api:map_tiles:sprite_sheet"
    url = "/api/map_tiles/sprites/{sprite_set}/{name}.png"
    content_type = "image/png"
    store_encoded = False
    extension = ".png"


class MapTilesTileJsonView(_MapTilesView):
    """Serve the TileJSON, rewritten to point back at this instance."""

    name = "api:map_tiles:tilejson"
    url = "/api/map_tiles/tilejson.json"
    content_type = "application/json"
    ttl = TILEJSON_TTL
    max_age = TILEJSON_MAX_AGE

    async def get(self, request: web.Request) -> web.StreamResponse:
        """Handle a GET request for the TileJSON."""
        self._authenticate(request)
        return await self._async_serve(request, "tilejson.json", TILEJSON_URL)

    @override
    async def _async_fetch(self, url: str) -> Asset | None:
        """Fetch the upstream TileJSON and republish it as ours.

        Generated from theirs rather than written by hand: the OSMF asks
        consumers to resolve tiles through it so they can move them.
        """
        if (asset := await super()._async_fetch(url)) is None:
            return None

        try:
            tilejson = json.loads(
                gzip.decompress(asset.body) if asset.encoding else asset.body
            )
        except ValueError:
            _LOGGER.error("Upstream TileJSON is not valid JSON")
            return None

        if not isinstance(tilejson, dict) or not tilejson.get("tiles"):
            _LOGGER.error("Upstream TileJSON does not list any tiles")
            return None

        # Ours to build, so this is the one thing compressed here.
        return Asset(
            gzip.compress(
                json_bytes(
                    {
                        **tilejson,
                        "tiles": [VECTOR_TILE_PATH],
                        # Clamped to what the tile view will actually serve.
                        "minzoom": max(tilejson.get("minzoom", 0), 0),
                        "maxzoom": min(
                            tilejson.get("maxzoom", VECTOR_MAX_ZOOM), VECTOR_MAX_ZOOM
                        ),
                        "attribution": ATTRIBUTION,
                    }
                ),
                mtime=0,
            ),
            GZIP,
        )
