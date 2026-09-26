"""The tests for http static files."""

from http import HTTPStatus
from pathlib import Path

from aiohttp.hdrs import CACHE_CONTROL
from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components.http import DOMAIN, StaticPathConfig
from homeassistant.components.http.static import CACHE_HEADER, CachingStaticResource
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant
from homeassistant.helpers.http import KEY_ALLOW_CONFIGURED_CORS
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def http(hass: HomeAssistant) -> None:
    """Ensure http is set up."""
    assert await async_setup_component(hass, DOMAIN, {})
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()


@pytest.fixture
async def mock_http_client(hass: HomeAssistant, aiohttp_client: ClientSessionGenerator):
    """Start the Home Assistant HTTP component."""
    return await aiohttp_client(hass.http.app, server_kwargs={"skip_url_asserts": True})


async def test_static_resource_show_index(
    hass: HomeAssistant, mock_http_client: TestClient, tmp_path: Path
) -> None:
    """Test static resource will return a directory index."""
    app = hass.http.app

    resource = CachingStaticResource("/", tmp_path, show_index=True)
    app.router.register_resource(resource)
    app[KEY_ALLOW_CONFIGURED_CORS](resource)

    resp = await mock_http_client.get("/")
    assert resp.status == 200
    assert resp.content_type == "text/html"


async def test_async_register_static_paths(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test registering multiple static paths."""
    assert await async_setup_component(hass, "frontend", {})
    path = str(Path(__file__).parent)
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig("/something", path),
            StaticPathConfig("/something_else", path),
        ]
    )

    client = await hass_client()
    resp = await client.get("/something/__init__.py")
    assert resp.status == HTTPStatus.OK
    resp = await client.get("/something_else/__init__.py")
    assert resp.status == HTTPStatus.OK


async def test_caching_static_resource_no_cache_header_on_404(
    hass: HomeAssistant, mock_http_client: TestClient, tmp_path: Path
) -> None:
    """Test the caching static resource sends no cache header on a 404."""
    app = hass.http.app

    resource = CachingStaticResource("/static", tmp_path)
    app.router.register_resource(resource)
    app[KEY_ALLOW_CONFIGURED_CORS](resource)

    (tmp_path / "exists.js").write_text("console.log('hi');", encoding="utf-8")

    resp = await mock_http_client.get("/static/exists.js")
    assert resp.status == HTTPStatus.OK
    assert resp.headers[CACHE_CONTROL] == CACHE_HEADER

    # A missing file answers 404 without a cache header so clients don't
    # cache the 404; the miss is not learned by the response cache either.
    resp = await mock_http_client.get("/static/does-not-exist.js")
    assert resp.status == HTTPStatus.NOT_FOUND
    assert CACHE_CONTROL not in resp.headers

    resp = await mock_http_client.get("/static/does-not-exist.js")
    assert resp.status == HTTPStatus.NOT_FOUND
    assert CACHE_CONTROL not in resp.headers

    # A file created at the same path after the 404 is served normally,
    # proving the miss was not retained in the response cache.
    (tmp_path / "does-not-exist.js").write_text(
        "console.log('late');", encoding="utf-8"
    )
    resp = await mock_http_client.get("/static/does-not-exist.js")
    assert resp.status == HTTPStatus.OK
    assert resp.headers[CACHE_CONTROL] == CACHE_HEADER
