"""HTTP views for the Map tiles integration."""

from functools import partial
import gzip
from http import HTTPStatus
import json
import logging
from typing import Final, override
import zlib

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
    DATA_ACCESS_TOKENS,
    FONTSTACK_RE,
    GLYPH_RANGE_RE,
    MAX_DECOMPRESSED_BYTES,
    MAX_FETCH_BYTES,
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

# A root-relative path works behind any reverse proxy; an absolute URL built
# from the request's Host header would not if the proxy does not forward it.
VECTOR_TILE_PATH = "/api/map_tiles/vector/{z}/{x}/{y}.mvt"

# Cap coordinate length before int(), which is expensive on huge digit strings.
MAX_COORDINATE_DIGITS = 8

GZIP: Final = "gzip"


def _gzip_decompress(body: bytes) -> bytes:
    """Decompress a gzip body, refusing pathological expansion."""
    decompressor = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
    decompressed = decompressor.decompress(body, MAX_DECOMPRESSED_BYTES)
    if decompressor.unconsumed_tail:
        raise ValueError("Decompressed body too large")
    if not decompressor.eof or decompressor.unused_data:
        raise ValueError("Malformed gzip body")
    return decompressed


def _upstream_ttl(cache_control: str) -> float | None:
    """Return upstream's max-age in seconds, or None when it sends none."""
    for directive in cache_control.split(","):
        name, _, value = directive.strip().partition("=")
        if name.lower() == "max-age" and value.isdigit():
            return float(value)
    return None


class _MapTilesView(HomeAssistantView):
    """Serve one class of map asset, from the cache or from upstream."""

    requires_auth = False

    content_type: str
    ttl: int
    max_age: int

    def __init__(self, hass: HomeAssistant, cache: MapTilesCache) -> None:
        """Initialize the view."""
        self._hass = hass
        self._cache = cache

    def _authenticate(self, request: web.Request) -> None:
        """Authenticate via the standard middleware or a map tiles query token."""
        access_tokens = self._hass.data[DATA_ACCESS_TOKENS]
        if request[KEY_AUTHENTICATED] or request.query.get("token") in access_tokens:
            return
        if hdrs.AUTHORIZATION in request.headers:
            # A real Bearer attempt, so let the ban middleware count it.
            raise web.HTTPUnauthorized
        # Most likely a query token that expired while a dashboard sat open, so
        # 403 rather than banning the user's own IP over it.
        raise web.HTTPForbidden

    async def _async_serve(self, key: str, url: str) -> web.Response:
        """Serve an asset from the cache, fetching it upstream on a miss.

        A gzip-encoded asset is served compressed to every client; Accept-Encoding
        is intentionally not checked, since every browser accepts gzip. There is
        therefore no identity variant, and hence no Vary on Accept-Encoding.
        """
        asset = await self._cache.async_get(
            key, self.ttl, partial(self._async_fetch, url)
        )
        if asset is None:
            return web.Response(status=HTTPStatus.BAD_GATEWAY)

        headers = {hdrs.CACHE_CONTROL: f"private, max-age={self.max_age}"}
        if asset.encoding:
            headers[hdrs.CONTENT_ENCODING] = asset.encoding

        return web.Response(
            body=asset.body, content_type=self.content_type, headers=headers
        )

    async def _async_fetch(self, url: str) -> Asset | None:
        """Fetch url upstream, returning None on any upstream failure."""
        session = async_get_clientsession(self._hass)
        # Keep the body in the encoding upstream sent, so a gzipped asset is
        # cached compressed instead of re-compressed for every client.
        try:
            async with session.get(
                url,
                headers=UPSTREAM_HEADERS,
                timeout=UPSTREAM_TIMEOUT,
                auto_decompress=False,
            ) as response:
                if response.status >= HTTPStatus.BAD_REQUEST:
                    _LOGGER.debug("Upstream %s returned %s", url, response.status)
                    return None
                # Accumulated in chunks so a hostile upstream cannot make this
                # process buffer an arbitrarily large response. An empty body
                # is a legitimate answer: a vector tile with nothing in it
                # comes back as a short 200, not a 204 or a 404.
                chunks: list[bytes] = []
                read = 0
                async for chunk in response.content.iter_chunked(64 * 1024):
                    read += len(chunk)
                    if read > MAX_FETCH_BYTES:
                        _LOGGER.warning(
                            "Upstream %s body exceeds %s bytes, refusing it",
                            url,
                            MAX_FETCH_BYTES,
                        )
                        return None
                    chunks.append(chunk)
        except (ClientError, TimeoutError) as err:
            _LOGGER.debug("Upstream %s failed: %s", url, err)
            return None

        body = b"".join(chunks)
        ttl = _upstream_ttl(response.headers.get(hdrs.CACHE_CONTROL, ""))
        return Asset(body, response.headers.get(hdrs.CONTENT_ENCODING), ttl)


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
    max_zoom = RASTER_MAX_ZOOM
    upstream = f"{RASTER_URL}/{{z}}/{{x}}/{{y}}.png"
    key_template = "raster/{z}/{x}/{y}.png"


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
        return await self._async_serve(path, f"{VECTOR_URL}/styles/shortbread/{path}")


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
        return await self._async_serve("tilejson.json", TILEJSON_URL)

    @override
    async def _async_fetch(self, url: str) -> Asset | None:
        """Fetch the upstream TileJSON and republish it as ours.

        The zoom range is taken from upstream (clamped to what we serve); the
        attribution and the advertised tile endpoint are replaced with this
        proxy's own. The tile endpoint is pinned, so the vector fetch URL does
        not follow the upstream template.
        """
        if (asset := await super()._async_fetch(url)) is None:
            return None
        return await self._hass.async_add_executor_job(self._rebuild, asset)

    def _rebuild(self, asset: Asset) -> Asset | None:
        """Rewrite the upstream TileJSON to point back at this instance."""
        try:
            tilejson = json.loads(
                _gzip_decompress(asset.body) if asset.encoding else asset.body
            )
        except ValueError, zlib.error:
            _LOGGER.error("Upstream TileJSON is not valid JSON")
            return None

        if not isinstance(tilejson, dict) or not tilejson.get("tiles"):
            _LOGGER.error("Upstream TileJSON does not list any tiles")
            return None

        try:
            # Clamped to what the tile view will actually serve.
            minzoom = max(int(tilejson.get("minzoom", 0)), 0)
            maxzoom = min(
                int(tilejson.get("maxzoom", VECTOR_MAX_ZOOM)), VECTOR_MAX_ZOOM
            )
        except TypeError, ValueError, OverflowError:
            _LOGGER.error("Upstream TileJSON zoom range is not a finite number")
            return None

        # The only body built locally, so the only one this integration gzips.
        # Kept on upstream's refresh cadence: it is how a moved endpoint arrives.
        return Asset(
            gzip.compress(
                json_bytes(
                    {
                        **tilejson,
                        "tiles": [VECTOR_TILE_PATH],
                        "minzoom": minzoom,
                        "maxzoom": maxzoom,
                        "attribution": ATTRIBUTION,
                    }
                ),
                mtime=0,
            ),
            GZIP,
            asset.ttl,
        )
