"""The tests for http static files."""

from pathlib import Path

from aiohttp.test_utils import TestClient
from aiohttp.web_exceptions import HTTPForbidden
import pytest

from homeassistant.components.http.static import CachingStaticResource, _get_file_path
from homeassistant.core import EVENT_HOMEASSISTANT_START, HomeAssistant
from homeassistant.helpers.http import KEY_ALLOW_CONFIGRED_CORS
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def http(hass: HomeAssistant) -> None:
    """Ensure http is set up."""
    assert await async_setup_component(hass, "http", {})
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()


@pytest.fixture
async def mock_http_client(hass: HomeAssistant, aiohttp_client: ClientSessionGenerator):
    """Start the Home Assistant HTTP component."""
    return await aiohttp_client(hass.http.app, server_kwargs={"skip_url_asserts": True})


@pytest.mark.parametrize(
    ("url", "canonical_url"),
    [
        ("//a", "//a"),
        ("///a", "///a"),
        ("/c:\\a\\b", "/c:%5Ca%5Cb"),
    ],
)
async def test_static_path_blocks_anchors(
    hass: HomeAssistant,
    mock_http_client: TestClient,
    tmp_path: Path,
    url: str,
    canonical_url: str,
) -> None:
    """Test static paths block anchors."""
    app = hass.http.app

    resource = CachingStaticResource(url, str(tmp_path))
    assert resource.canonical == canonical_url
    app.router.register_resource(resource)
    app[KEY_ALLOW_CONFIGRED_CORS](resource)

    resp = await mock_http_client.get(canonical_url, allow_redirects=False)
    assert resp.status == 403

    # Tested directly since aiohttp will block it before
    # it gets here but we want to make sure if aiohttp ever
    # changes we still block it.
    with pytest.raises(HTTPForbidden):
        _get_file_path(canonical_url, tmp_path)
