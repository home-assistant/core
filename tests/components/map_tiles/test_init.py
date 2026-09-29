"""Tests for the Map tiles integration."""

from datetime import timedelta
import gzip
from http import HTTPStatus
import math
from unittest.mock import patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.map_tiles.const import (
    ASSET_MAX_AGE,
    ATTRIBUTION,
    DATA_ACCESS_TOKENS,
    DOMAIN,
    RASTER_URL,
    TILE_MAX_AGE,
    TILEJSON_URL,
    TOKEN_CHANGE_INTERVAL,
    VECTOR_URL,
)
from homeassistant.components.map_tiles.views import MapTilesVectorView
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator, WebSocketGenerator

VECTOR_TILE = b"\x1a\x0fnot-really-a-mvt"
RASTER_TILE = b"\x89PNG\r\n\x1a\nnot-really-a-png"
GLYPHS = b"not-really-a-glyph-range"
SPRITES = b"\x89PNG\r\n\x1a\nnot-really-a-sprite-sheet"

VECTOR_PATH = "/api/map_tiles/vector/12/2048/1361.mvt"
RASTER_PATH = "/api/map_tiles/raster/12/2048/1361.png"
GLYPHS_PATH = "/api/map_tiles/fonts/noto_sans_regular/0-255.pbf"
TILEJSON_PATH = "/api/map_tiles/tilejson.json"

VECTOR_UPSTREAM = f"{VECTOR_URL}/shortbread_v1/12/2048/1361.mvt"
RASTER_UPSTREAM = f"{RASTER_URL}/12/2048/1361.png"
GLYPHS_UPSTREAM = f"{VECTOR_URL}/styles/shortbread/fonts/noto_sans_regular/0-255.pbf"

UPSTREAM_TILEJSON = {
    "tilejson": "3.0.0",
    "name": "shortbread",
    "tiles": [f"{VECTOR_URL}/shortbread_v1/{{z}}/{{x}}/{{y}}.mvt"],
    "minzoom": 0,
    "maxzoom": 14,
    "attribution": (
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    ),
    "vector_layers": [{"id": "ocean"}],
}


@pytest.fixture(autouse=True)
async def setup_map_tiles(hass: HomeAssistant) -> None:
    """Set up the integration for every test."""
    assert await async_setup_component(hass, "http", {"http": {}})
    assert await async_setup_component(hass, DOMAIN, {})


async def test_vector_tile(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test serving a vector tile."""
    aioclient_mock.get(VECTOR_UPSTREAM, content=VECTOR_TILE)

    client = await hass_client()
    resp = await client.get(VECTOR_PATH)

    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "application/vnd.mapbox-vector-tile"
    assert resp.headers["Cache-Control"] == f"private, max-age={TILE_MAX_AGE}"
    assert await resp.read() == VECTOR_TILE


async def test_raster_tile(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test serving a raster tile."""
    aioclient_mock.get(RASTER_UPSTREAM, content=RASTER_TILE)

    client = await hass_client()
    resp = await client.get(RASTER_PATH)

    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "image/png"
    assert await resp.read() == RASTER_TILE


async def test_glyphs(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test serving a glyph range."""
    aioclient_mock.get(GLYPHS_UPSTREAM, content=GLYPHS)

    client = await hass_client()
    resp = await client.get(GLYPHS_PATH)

    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "application/x-protobuf"
    assert resp.headers["Cache-Control"] == f"private, max-age={ASSET_MAX_AGE}"
    assert await resp.read() == GLYPHS


@pytest.mark.parametrize(
    ("name", "content_type"),
    [
        ("sprites.json", "application/json"),
        ("sprites@2x.json", "application/json"),
        ("sprites.png", "image/png"),
        ("sprites@2x.png", "image/png"),
    ],
)
async def test_sprites(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    name: str,
    content_type: str,
) -> None:
    """Test serving the sprite index and sheet, at both scales."""
    aioclient_mock.get(
        f"{VECTOR_URL}/styles/shortbread/sprites/basics/{name}", content=SPRITES
    )

    client = await hass_client()
    resp = await client.get(f"/api/map_tiles/sprites/basics/{name}")

    assert resp.status == HTTPStatus.OK
    assert resp.content_type == content_type
    assert await resp.read() == SPRITES


async def test_compressed_tile_is_handed_on_as_it_arrived(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a tile is compressed upstream once, not here for every client."""
    tile = b"a vector tile large enough to be worth compressing" * 100
    aioclient_mock.get(
        VECTOR_UPSTREAM,
        content=gzip.compress(tile),
        headers={"Content-Encoding": "gzip"},
    )

    client = await hass_client()
    resp = await client.get(VECTOR_PATH)

    assert resp.status == HTTPStatus.OK
    assert resp.headers["Content-Encoding"] == "gzip"
    assert "Vary" not in resp.headers
    # The test client decompresses on read; a stale `Content-Encoding` over
    # already-decoded bytes would make this read fail.
    assert await resp.read() == tile


async def test_gzip_is_served_regardless_of_accept_encoding(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a stored gzip asset is served compressed even for an identity request."""
    tile = b"a vector tile large enough to be worth compressing" * 100
    aioclient_mock.get(
        VECTOR_UPSTREAM,
        content=gzip.compress(tile),
        headers={"Content-Encoding": "gzip"},
    )

    client = await hass_client()
    resp = await client.get(VECTOR_PATH, headers={"Accept-Encoding": "identity"})

    assert resp.status == HTTPStatus.OK
    assert resp.headers["Content-Encoding"] == "gzip"
    # The test client decompresses on read regardless of what it requested.
    assert await resp.read() == tile


async def test_png_served_verbatim(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a raster tile is served exactly as upstream sent it."""
    aioclient_mock.get(RASTER_UPSTREAM, content=RASTER_TILE)

    client = await hass_client()
    resp = await client.get(RASTER_PATH)

    assert resp.status == HTTPStatus.OK
    assert "Content-Encoding" not in resp.headers
    assert await resp.read() == RASTER_TILE


async def test_upstream_headers_identify_home_assistant(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the upstream request says who is asking, and nothing else."""
    aioclient_mock.get(RASTER_UPSTREAM, content=RASTER_TILE)

    client = await hass_client()
    await client.get(RASTER_PATH)

    headers = aioclient_mock.mock_calls[0][3]
    assert headers["User-Agent"].startswith("HomeAssistant/")
    assert "abuse@home-assistant.io" in headers["User-Agent"]
    # Pinned to gzip so cached bodies are in an encoding every client accepts.
    assert headers["Accept-Encoding"] == "gzip"
    # A Referer would be the instance hostname, which identifies an installation.
    assert "Referer" not in headers
    assert "Cookie" not in headers
    assert "X-Requested-With" not in headers


async def test_tilejson_is_rewritten(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the TileJSON points back at this instance and credits OSM."""
    aioclient_mock.get(TILEJSON_URL, json=UPSTREAM_TILEJSON)

    client = await hass_client()
    resp = await client.get(TILEJSON_PATH)

    assert resp.status == HTTPStatus.OK
    tilejson = await resp.json()
    assert tilejson["tiles"] == ["/api/map_tiles/vector/{z}/{x}/{y}.mvt"]
    assert tilejson["attribution"] == ATTRIBUTION
    assert "contributors" in tilejson["attribution"]
    assert tilejson["minzoom"] == 0
    assert tilejson["maxzoom"] == 14
    # Passed through, so a change upstream needs no release here.
    assert tilejson["vector_layers"] == [{"id": "ocean"}]


async def test_tilejson_maxzoom_is_clamped(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the advertised zoom range cannot exceed what is served."""
    aioclient_mock.get(TILEJSON_URL, json={**UPSTREAM_TILEJSON, "maxzoom": 20})

    client = await hass_client()
    resp = await client.get(TILEJSON_PATH)

    assert (await resp.json())["maxzoom"] == 14


@pytest.mark.parametrize(
    "upstream",
    [
        pytest.param({"text": "<html>not json</html>"}, id="not json"),
        pytest.param({"json": {"tiles": []}}, id="no tiles"),
        pytest.param({"json": {}}, id="empty"),
        pytest.param({"json": ["not", "an", "object"]}, id="not an object"),
        pytest.param(
            {"content": b"not gzip", "headers": {"Content-Encoding": "gzip"}},
            id="lying content encoding",
        ),
        pytest.param(
            {"json": {**UPSTREAM_TILEJSON, "minzoom": "low"}},
            id="minzoom not numeric",
        ),
        pytest.param(
            {"json": {**UPSTREAM_TILEJSON, "maxzoom": None}},
            id="maxzoom not numeric",
        ),
        pytest.param(
            {"json": {**UPSTREAM_TILEJSON, "minzoom": math.inf}},
            id="minzoom not finite",
        ),
    ],
)
async def test_tilejson_unusable(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    upstream: dict[str, object],
) -> None:
    """Test that a TileJSON we cannot use is refused rather than passed on."""
    aioclient_mock.get(TILEJSON_URL, **upstream)

    client = await hass_client()
    resp = await client.get(TILEJSON_PATH)

    assert resp.status == HTTPStatus.BAD_GATEWAY


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/api/map_tiles/vector/15/16384/10888.mvt", id="vector above z14"),
        pytest.param(
            "/api/map_tiles/raster/20/524288/348416.png", id="raster above z19"
        ),
        pytest.param("/api/map_tiles/vector/2/4/1.mvt", id="x outside the pyramid"),
        pytest.param("/api/map_tiles/vector/2/1/4.mvt", id="y outside the pyramid"),
        pytest.param("/api/map_tiles/vector/1/123456789/1.mvt", id="absurd coordinate"),
        pytest.param("/api/map_tiles/vector/a/1/1.mvt", id="non numeric coordinate"),
        pytest.param("/api/map_tiles/fonts/../../etc/passwd/0-255.pbf", id="traversal"),
        pytest.param("/api/map_tiles/fonts/noto_sans/nonsense.pbf", id="bad range"),
        pytest.param("/api/map_tiles/fonts/noto_sans/0-255.exe", id="bad extension"),
        pytest.param("/api/map_tiles/sprites/BASICS/sprites.png", id="bad sprite set"),
        pytest.param("/api/map_tiles/sprites/basics/other.png", id="bad sprite name"),
    ],
)
async def test_rejected_before_upstream(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    path: str,
) -> None:
    """Test that a request we cannot serve never reaches the OSMF."""
    client = await hass_client()
    resp = await client.get(path)

    assert resp.status == HTTPStatus.NOT_FOUND
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    ("path", "upstream_url", "failure"),
    [
        pytest.param(
            VECTOR_PATH,
            VECTOR_UPSTREAM,
            {"status": HTTPStatus.INTERNAL_SERVER_ERROR},
            id="vector 500",
        ),
        pytest.param(
            VECTOR_PATH,
            VECTOR_UPSTREAM,
            {"status": HTTPStatus.NOT_FOUND},
            id="vector 404",
        ),
        pytest.param(
            VECTOR_PATH, VECTOR_UPSTREAM, {"exc": ClientError}, id="vector unreachable"
        ),
        pytest.param(
            VECTOR_PATH, VECTOR_UPSTREAM, {"exc": TimeoutError}, id="vector timeout"
        ),
        pytest.param(
            RASTER_PATH, RASTER_UPSTREAM, {"exc": ClientError}, id="raster unreachable"
        ),
        pytest.param(
            TILEJSON_PATH, TILEJSON_URL, {"exc": ClientError}, id="tilejson unreachable"
        ),
        pytest.param(
            GLYPHS_PATH,
            GLYPHS_UPSTREAM,
            {"status": HTTPStatus.INTERNAL_SERVER_ERROR},
            id="glyphs 500",
        ),
    ],
)
async def test_upstream_failure(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    path: str,
    upstream_url: str,
    failure: dict[str, object],
) -> None:
    """Test that an upstream failure is reported rather than remembered."""
    aioclient_mock.get(upstream_url, **failure)

    client = await hass_client()
    assert (await client.get(path)).status == HTTPStatus.BAD_GATEWAY
    assert (await client.get(path)).status == HTTPStatus.BAD_GATEWAY
    assert aioclient_mock.call_count == 2


async def test_empty_vector_tile_is_served(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a tile with nothing in it is an answer, not a failure."""
    aioclient_mock.get(VECTOR_UPSTREAM, content=b"")

    client = await hass_client()
    resp = await client.get(VECTOR_PATH)

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == b""


async def test_oversized_upstream_body_is_refused(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a body larger than the fetch cap is refused rather than held."""
    aioclient_mock.get(VECTOR_UPSTREAM, content=b"x" * 200)

    client = await hass_client()
    with patch("homeassistant.components.map_tiles.views.MAX_FETCH_BYTES", 100):
        assert (await client.get(VECTOR_PATH)).status == HTTPStatus.BAD_GATEWAY
        # Not cached, so the second request has to go out again.
        assert (await client.get(VECTOR_PATH)).status == HTTPStatus.BAD_GATEWAY

    assert aioclient_mock.call_count == 2


async def test_tilejson_expanding_past_the_cap_is_refused(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a TileJSON whose gzip body expands past the cap is refused."""
    aioclient_mock.get(
        TILEJSON_URL,
        content=gzip.compress(b"0" * 1000),
        headers={"Content-Encoding": "gzip"},
    )

    client = await hass_client()
    with patch("homeassistant.components.map_tiles.views.MAX_DECOMPRESSED_BYTES", 100):
        resp = await client.get(TILEJSON_PATH)

    assert resp.status == HTTPStatus.BAD_GATEWAY


async def test_cached_tile_is_not_fetched_again(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a second request for a tile is served from the cache."""
    aioclient_mock.get(VECTOR_UPSTREAM, content=VECTOR_TILE)

    client = await hass_client()
    assert (await client.get(VECTOR_PATH)).status == HTTPStatus.OK
    assert (await client.get(VECTOR_PATH)).status == HTTPStatus.OK

    assert aioclient_mock.call_count == 1


# Shortened so the frozen clock can pass a tile's TTL without also passing the
# lifetime of the test client's own access token.
SHORT_TTL = 5


async def test_stale_tile_is_served_while_it_refreshes(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an expired tile is served now and replaced behind the response."""
    aioclient_mock.get(VECTOR_UPSTREAM, content=VECTOR_TILE)

    client = await hass_client()
    with patch.object(MapTilesVectorView, "ttl", SHORT_TTL):
        assert await (await client.get(VECTOR_PATH)).read() == VECTOR_TILE

        freezer.tick(SHORT_TTL + 1)
        aioclient_mock.clear_requests()
        aioclient_mock.get(VECTOR_UPSTREAM, content=b"a newer tile")

        # The stale bytes come back straight away rather than waiting on upstream.
        assert await (await client.get(VECTOR_PATH)).read() == VECTOR_TILE
        await hass.async_block_till_done()

        assert aioclient_mock.call_count == 1
        assert await (await client.get(VECTOR_PATH)).read() == b"a newer tile"


async def test_stale_tile_survives_an_upstream_outage(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an unreachable upstream degrades to old tiles, not to no map."""
    aioclient_mock.get(VECTOR_UPSTREAM, content=VECTOR_TILE)

    client = await hass_client()
    with patch.object(MapTilesVectorView, "ttl", SHORT_TTL):
        assert await (await client.get(VECTOR_PATH)).read() == VECTOR_TILE

        freezer.tick(SHORT_TTL + 1)
        aioclient_mock.clear_requests()
        aioclient_mock.get(VECTOR_UPSTREAM, exc=ClientError)

        resp = await client.get(VECTOR_PATH)
        await hass.async_block_till_done()

        assert resp.status == HTTPStatus.OK
        assert await resp.read() == VECTOR_TILE
        assert await (await client.get(VECTOR_PATH)).read() == VECTOR_TILE


async def test_upstream_max_age_drives_the_refresh(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that upstream's Cache-Control max-age, not the fallback TTL, refreshes."""
    aioclient_mock.get(
        VECTOR_UPSTREAM, content=VECTOR_TILE, headers={"Cache-Control": "max-age=5"}
    )

    client = await hass_client()
    assert await (await client.get(VECTOR_PATH)).read() == VECTOR_TILE

    # Past upstream's 5 s max-age but far below the multi-day fallback TTL.
    freezer.tick(6)
    aioclient_mock.clear_requests()
    aioclient_mock.get(VECTOR_UPSTREAM, content=b"a newer tile")

    assert await (await client.get(VECTOR_PATH)).read() == VECTOR_TILE
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 1
    assert await (await client.get(VECTOR_PATH)).read() == b"a newer tile"


async def test_token_query_param_authenticates(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a token in the query string authenticates, as an <img> must."""
    aioclient_mock.get(RASTER_UPSTREAM, content=RASTER_TILE)

    token = hass.data[DATA_ACCESS_TOKENS][-1]
    client = await hass_client_no_auth()
    resp = await client.get(f"{RASTER_PATH}?token={token}")

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == RASTER_TILE


async def test_both_live_tokens_authenticate(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a URL minted before the last rotation still loads."""
    aioclient_mock.get(RASTER_UPSTREAM, content=RASTER_TILE)
    client = await hass_client_no_auth()

    freezer.tick(TOKEN_CHANGE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    tokens = hass.data[DATA_ACCESS_TOKENS]
    assert len(tokens) == 2
    for token in tokens:
        resp = await client.get(f"{RASTER_PATH}?token={token}")
        assert resp.status == HTTPStatus.OK


async def test_rotated_out_token_is_rejected(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a token stops authenticating once two rotations have passed."""
    client = await hass_client_no_auth()
    token = hass.data[DATA_ACCESS_TOKENS][-1]

    for _ in range(2):
        freezer.tick(TOKEN_CHANGE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    resp = await client.get(f"{RASTER_PATH}?token={token}")
    assert resp.status == HTTPStatus.FORBIDDEN


@pytest.mark.parametrize(
    "path",
    [VECTOR_PATH, RASTER_PATH, GLYPHS_PATH, TILEJSON_PATH],
)
async def test_unauthenticated_request_is_forbidden(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    path: str,
) -> None:
    """Test that an internet exposed instance is not an open tile proxy."""
    client = await hass_client_no_auth()
    resp = await client.get(path)

    assert resp.status == HTTPStatus.FORBIDDEN
    assert aioclient_mock.call_count == 0


async def test_invalid_token_is_forbidden(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test that a wrong query token does not count as a failed login."""
    client = await hass_client_no_auth()
    resp = await client.get(f"{RASTER_PATH}?token=not-a-token")

    assert resp.status == HTTPStatus.FORBIDDEN


async def test_invalid_bearer_token_is_unauthorized(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test that a real Bearer attempt is a 401, so the ban middleware sees it."""
    client = await hass_client_no_auth()
    resp = await client.get(
        RASTER_PATH, headers={"Authorization": "Bearer not-a-token"}
    )

    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_ws_access_token(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test handing the current token to the frontend."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "map_tiles/access_token"})
    first = (await client.receive_json())["result"]["token"]
    assert first == hass.data[DATA_ACCESS_TOKENS][-1]

    freezer.tick(TOKEN_CHANGE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "map_tiles/access_token"})
    assert (await client.receive_json())["result"]["token"] != first
