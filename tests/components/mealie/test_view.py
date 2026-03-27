"""Tests for the Mealie image proxy view."""

import asyncio
from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
import pytest

from homeassistant.components.mealie.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

HOST = "http://demo.mealie.io"
ENTRY_ID = "01J0BC4QM2YBRP6H5G933CETT7"
RECIPE_ID = "c5f00a93-71a2-4e48-900f-d9ad0bb9de93"
IMAGE_URL = f"{HOST}/api/media/recipes/{RECIPE_ID}/images/original.webp"
PROXY_URL = f"/api/mealie_image_proxy/{ENTRY_ID}/{RECIPE_ID}"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry with a full URL scheme for view tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Mealie",
        data={CONF_HOST: HOST, CONF_API_TOKEN: "token"},
        entry_id=ENTRY_ID,
        unique_id="bf1c62fe-4941-4332-9886-e54e88dbdba0",
    )


@pytest.fixture(autouse=True)
def no_platforms() -> Generator[None]:
    """Disable platform setup for view tests (view is registered in async_setup)."""
    with patch(
        "homeassistant.components.mealie.PLATFORMS",
        [],
    ):
        yield


async def test_view_proxies_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the view proxies the image from Mealie."""
    aioclient_mock.get(
        IMAGE_URL,
        content=b"fake_webp_data",
        headers={"Content-Type": "image/webp"},
    )

    await setup_integration(hass, mock_config_entry)

    client = await hass_client()
    response = await client.get(PROXY_URL)

    assert response.status == HTTPStatus.OK
    assert await response.read() == b"fake_webp_data"
    assert response.headers["Content-Type"] == "image/webp"
    assert response.headers["Cache-Control"] == "max-age=3600"


async def test_view_returns_not_found_for_wrong_domain_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the view returns 404 for a config entry from a different domain."""
    other_entry = MockConfigEntry(
        domain="other_integration",
        title="Other",
        data={},
    )
    other_entry.add_to_hass(hass)
    await setup_integration(hass, mock_config_entry)

    client = await hass_client()
    response = await client.get(
        f"/api/mealie_image_proxy/{other_entry.entry_id}/{RECIPE_ID}"
    )
    assert response.status == HTTPStatus.NOT_FOUND


async def test_view_returns_not_found_for_unknown_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the view returns 404 for an unknown config entry."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_client()
    response = await client.get(f"/api/mealie_image_proxy/unknown_entry/{RECIPE_ID}")

    assert response.status == HTTPStatus.NOT_FOUND


async def test_view_returns_not_found_when_mealie_errors(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the view returns 404 when Mealie returns a non-200 status."""
    aioclient_mock.get(IMAGE_URL, status=HTTPStatus.NOT_FOUND)

    await setup_integration(hass, mock_config_entry)

    client = await hass_client()
    response = await client.get(PROXY_URL)

    assert response.status == HTTPStatus.NOT_FOUND


async def test_view_returns_unavailable_on_client_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the view returns 503 when a network error occurs."""
    aioclient_mock.get(IMAGE_URL, exc=ClientError)

    await setup_integration(hass, mock_config_entry)

    client = await hass_client()
    response = await client.get(PROXY_URL)

    assert response.status == HTTPStatus.SERVICE_UNAVAILABLE


async def test_view_returns_bad_gateway_for_invalid_content_type(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the view returns 502 for an unexpected content-type."""
    aioclient_mock.get(
        IMAGE_URL,
        content=b"<html>not an image</html>",
        headers={"Content-Type": "text/html"},
    )
    await setup_integration(hass, mock_config_entry)

    client = await hass_client()
    response = await client.get(PROXY_URL)

    assert response.status == HTTPStatus.BAD_GATEWAY


async def test_view_returns_bad_gateway_for_oversized_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the view returns 502 when Content-Length exceeds the size limit."""
    aioclient_mock.get(
        IMAGE_URL,
        content=b"fake_webp_data",
        headers={
            "Content-Type": "image/webp",
            "Content-Length": str(11 * 1024 * 1024),  # 11 MiB > 10 MiB limit
        },
    )
    await setup_integration(hass, mock_config_entry)

    client = await hass_client()
    response = await client.get(PROXY_URL)

    assert response.status == HTTPStatus.BAD_GATEWAY


async def test_view_returns_unavailable_on_timeout(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the view returns 503 when a timeout occurs."""
    aioclient_mock.get(IMAGE_URL, exc=asyncio.TimeoutError)

    await setup_integration(hass, mock_config_entry)

    client = await hass_client()
    response = await client.get(PROXY_URL)

    assert response.status == HTTPStatus.SERVICE_UNAVAILABLE


async def test_view_rejects_unauthenticated(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the view returns 403 for requests without credentials."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_client_no_auth()
    response = await client.get(PROXY_URL)

    assert response.status == HTTPStatus.FORBIDDEN


async def test_view_rejects_invalid_bearer_token(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the view returns 401 when an invalid Bearer token is presented."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_client_no_auth()
    response = await client.get(
        PROXY_URL, headers={"Authorization": "Bearer invalid_token"}
    )

    assert response.status == HTTPStatus.UNAUTHORIZED
