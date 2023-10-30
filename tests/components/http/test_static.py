"""The tests for http static files."""


from pathlib import Path

from aiohttp.test_utils import TestClient
import pytest

from homeassistant.core import EVENT_HOMEASSISTANT_START, HomeAssistant
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
    return await aiohttp_client(hass.http.app)


async def test_static_path_blocks_anchors(
    hass: HomeAssistant, mock_http_client: TestClient, tmp_path: Path
) -> None:
    """Test static paths block anchors."""
    hass.http.register_static_path(r"/static/D:\path", str(tmp_path))

    resp = await mock_http_client.get(r"/static/D:\path", allow_redirects=False)
    assert resp.status == 403
