"""Test the brand icon serving."""

from http import HTTPStatus
from pathlib import Path

from aiohttp.test_utils import TestClient
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

from tests.common import MockModule, mock_integration
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture
async def frontend(hass: HomeAssistant) -> None:
    """Frontend setup."""
    assert await async_setup_component(hass, "frontend", {})


@pytest.fixture
async def mock_http_client(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator, frontend: None
) -> TestClient:
    """Start the Home Assistant HTTP component."""
    return await aiohttp_client(hass.http.app)


async def test_brands_local_icon(
    hass: HomeAssistant, mock_http_client: TestClient, tmp_path: Path
) -> None:
    """Test serving a local brand icon."""
    domain = "test_integration"
    filename = "icon.png"

    integration_path = tmp_path / domain
    integration_path.mkdir()
    icon_file = integration_path / filename
    icon_file.write_bytes(b"pseudo-png-content")

    mock_integration(hass, MockModule(domain), path=str(integration_path))

    # We need to make sure async_get_integration returns our mock integration with the correct path
    integration = await async_get_integration(hass, domain)
    assert str(integration.file_path) == str(integration_path)

    resp = await mock_http_client.get(f"/brands/{domain}/{filename}")
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == b"pseudo-png-content"


async def test_brands_proxy_external(
    hass: HomeAssistant,
    mock_http_client: TestClient,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test proxying to external brands service when local icon is missing."""
    domain = "test_integration"

    aioclient_mock.get(
        f"https://brands.home-assistant.io/_/{domain}/icon.png",
        content=b"proxied-content",
        status=200,
    )

    resp = await mock_http_client.get(f"/brands/{domain}/icon.png")
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == b"proxied-content"


async def test_brands_invalid_filename(
    hass: HomeAssistant, mock_http_client: TestClient
) -> None:
    """Test security checks for invalid filenames."""
    domain = "test_integration"

    mock_integration(hass, MockModule(domain))

    resp = await mock_http_client.get(f"/brands/{domain}/manifest.json")
    assert resp.status == HTTPStatus.FORBIDDEN


async def test_brands_dark_fallback(
    hass: HomeAssistant, mock_http_client: TestClient, tmp_path: Path
) -> None:
    """Test falling back to non-dark icon if dark icon is missing."""
    domain = "test_integration"
    dark_filename = "dark_icon.png"
    fallback_filename = "icon.png"

    integration_path = tmp_path / domain
    integration_path.mkdir()
    icon_file = integration_path / fallback_filename
    icon_file.write_bytes(b"fallback-content")

    mock_integration(hass, MockModule(domain), path=str(integration_path))

    resp = await mock_http_client.get(f"/brands/{domain}/{dark_filename}")
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == b"fallback-content"
