"""Tests for the Brands integration."""

from datetime import timedelta
from http import HTTPStatus
import os
from pathlib import Path
import time
from unittest.mock import patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.brands.const import (
    BRANDS_CDN_URL,
    CACHE_TTL,
    DOMAIN,
    TOKEN_CHANGE_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.loader import Integration
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator, WebSocketGenerator

FAKE_PNG = b"\x89PNG\r\n\x1a\nfakeimagedata"


@pytest.fixture(autouse=True)
async def setup_brands(hass: HomeAssistant) -> None:
    """Set up the brands integration for all tests."""
    assert await async_setup_component(hass, "http", {"http": {}})
    assert await async_setup_component(hass, DOMAIN, {})


def _create_custom_integration(
    hass: HomeAssistant,
    domain: str,
    *,
    has_branding: bool = False,
) -> Integration:
    """Create a mock custom integration."""
    top_level = {"__init__.py", "manifest.json"}
    if has_branding:
        top_level.add("brand")
    return Integration(
        hass,
        f"custom_components.{domain}",
        Path(hass.config.config_dir) / "custom_components" / domain,
        {
            "name": domain,
            "domain": domain,
            "config_flow": False,
            "dependencies": [],
            "requirements": [],
            "version": "1.0.0",
        },
        top_level,
    )


# ------------------------------------------------------------------
# Integration view: /api/brands/integration/{domain}/{image}
# ------------------------------------------------------------------


async def test_integration_view_serves_from_cdn(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test serving an integration brand image from the CDN."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/hue/icon.png",
        content=FAKE_PNG,
    )

    client = await hass_client()
    resp = await client.get("/api/brands/integration/hue/icon.png")

    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "image/png"
    assert await resp.read() == FAKE_PNG


async def test_integration_view_default_placeholder_fallback(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that CDN 404 serves placeholder by default."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/nonexistent/icon.png",
        status=HTTPStatus.NOT_FOUND,
    )
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/_/_placeholder/icon.png",
        content=FAKE_PNG,
    )

    client = await hass_client()
    resp = await client.get("/api/brands/integration/nonexistent/icon.png")

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == FAKE_PNG


async def test_integration_view_no_placeholder(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that CDN 404 returns 404 when placeholder=no is set."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/nonexistent/icon.png",
        status=HTTPStatus.NOT_FOUND,
    )

    client = await hass_client()
    resp = await client.get(
        "/api/brands/integration/nonexistent/icon.png?placeholder=no"
    )

    assert resp.status == HTTPStatus.NOT_FOUND


async def test_integration_view_invalid_domain(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that invalid domain names return 404."""
    client = await hass_client()

    resp = await client.get("/api/brands/integration/INVALID/icon.png")
    assert resp.status == HTTPStatus.NOT_FOUND

    resp = await client.get("/api/brands/integration/../etc/icon.png")
    assert resp.status == HTTPStatus.NOT_FOUND

    resp = await client.get("/api/brands/integration/has spaces/icon.png")
    assert resp.status == HTTPStatus.NOT_FOUND

    resp = await client.get("/api/brands/integration/_leading/icon.png")
    assert resp.status == HTTPStatus.NOT_FOUND

    resp = await client.get("/api/brands/integration/trailing_/icon.png")
    assert resp.status == HTTPStatus.NOT_FOUND

    resp = await client.get("/api/brands/integration/double__under/icon.png")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_integration_view_invalid_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that invalid image filenames return 404."""
    client = await hass_client()

    resp = await client.get("/api/brands/integration/hue/malicious.jpg")
    assert resp.status == HTTPStatus.NOT_FOUND

    resp = await client.get("/api/brands/integration/hue/../../etc/passwd")
    assert resp.status == HTTPStatus.NOT_FOUND

    resp = await client.get("/api/brands/integration/hue/notallowed.png")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_integration_view_all_allowed_images(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that all allowed image filenames are accepted."""
    allowed = [
        "icon.png",
        "logo.png",
        "icon@2x.png",
        "logo@2x.png",
        "dark_icon.png",
        "dark_logo.png",
        "dark_icon@2x.png",
        "dark_logo@2x.png",
    ]
    for image in allowed:
        aioclient_mock.get(
            f"{BRANDS_CDN_URL}/brands/hue/{image}",
            content=FAKE_PNG,
        )

    client = await hass_client()
    for image in allowed:
        resp = await client.get(f"/api/brands/integration/hue/{image}")
        assert resp.status == HTTPStatus.OK, f"Failed for {image}"


async def test_integration_view_cdn_error_returns_none(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that CDN connection errors result in 404 with placeholder=no."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/broken/icon.png",
        exc=ClientError(),
    )

    client = await hass_client()
    resp = await client.get("/api/brands/integration/broken/icon.png?placeholder=no")

    assert resp.status == HTTPStatus.NOT_FOUND


async def test_integration_view_cdn_unexpected_status(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that unexpected CDN status codes result in 404 with placeholder=no."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/broken/icon.png",
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    client = await hass_client()
    resp = await client.get("/api/brands/integration/broken/icon.png?placeholder=no")

    assert resp.status == HTTPStatus.NOT_FOUND


# ------------------------------------------------------------------
# Disk caching
# ------------------------------------------------------------------


async def test_disk_cache_hit(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a second request is served from disk cache."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/hue/icon.png",
        content=FAKE_PNG,
    )

    client = await hass_client()

    # First request: fetches from CDN
    resp = await client.get("/api/brands/integration/hue/icon.png")
    assert resp.status == HTTPStatus.OK
    assert aioclient_mock.call_count == 1

    # Second request: served from disk cache
    resp = await client.get("/api/brands/integration/hue/icon.png")
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == FAKE_PNG
    assert aioclient_mock.call_count == 1  # No additional CDN call


async def test_disk_cache_404_marker(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that 404s are cached as empty files."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/nothing/icon.png",
        status=HTTPStatus.NOT_FOUND,
    )

    client = await hass_client()

    # First request: CDN returns 404, cached as empty file
    resp = await client.get("/api/brands/integration/nothing/icon.png?placeholder=no")
    assert resp.status == HTTPStatus.NOT_FOUND
    assert aioclient_mock.call_count == 1

    # Second request: served from cached 404 marker
    resp = await client.get("/api/brands/integration/nothing/icon.png?placeholder=no")
    assert resp.status == HTTPStatus.NOT_FOUND
    assert aioclient_mock.call_count == 1  # No additional CDN call


async def test_stale_cache_triggers_background_refresh(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that stale cache entries trigger background refresh."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/hue/icon.png",
        content=FAKE_PNG,
    )

    client = await hass_client()

    # Prime the cache
    resp = await client.get("/api/brands/integration/hue/icon.png")
    assert resp.status == HTTPStatus.OK
    assert aioclient_mock.call_count == 1

    # Make the cache stale by backdating the file mtime
    cache_path = (
        Path(hass.config.cache_path(DOMAIN)) / "integrations" / "hue" / "icon.png"
    )
    assert cache_path.is_file()
    stale_time = time.time() - CACHE_TTL - 1
    os.utime(cache_path, (stale_time, stale_time))

    # Request with stale cache should still return cached data
    # but trigger a background refresh
    resp = await client.get("/api/brands/integration/hue/icon.png")
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == FAKE_PNG

    # Wait for the background task to complete
    await hass.async_block_till_done()

    # Background refresh should have fetched from CDN again
    assert aioclient_mock.call_count == 2


async def test_stale_cache_404_marker_with_placeholder(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that stale cached 404 serves placeholder by default."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/gone/icon.png",
        status=HTTPStatus.NOT_FOUND,
    )
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/_/_placeholder/icon.png",
        content=FAKE_PNG,
    )

    client = await hass_client()

    # First request caches the 404 (with placeholder=no)
    resp = await client.get("/api/brands/integration/gone/icon.png?placeholder=no")
    assert resp.status == HTTPStatus.NOT_FOUND
    assert aioclient_mock.call_count == 1

    # Make the cache stale
    cache_path = (
        Path(hass.config.cache_path(DOMAIN)) / "integrations" / "gone" / "icon.png"
    )
    assert cache_path.is_file()
    stale_time = time.time() - CACHE_TTL - 1
    os.utime(cache_path, (stale_time, stale_time))

    # Stale 404 with default placeholder serves the placeholder
    resp = await client.get("/api/brands/integration/gone/icon.png")
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == FAKE_PNG


async def test_stale_cache_404_marker_no_placeholder(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that stale cached 404 with placeholder=no returns 404."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/gone/icon.png",
        status=HTTPStatus.NOT_FOUND,
    )

    client = await hass_client()

    # First request caches the 404
    resp = await client.get("/api/brands/integration/gone/icon.png?placeholder=no")
    assert resp.status == HTTPStatus.NOT_FOUND
    assert aioclient_mock.call_count == 1

    # Make the cache stale
    cache_path = (
        Path(hass.config.cache_path(DOMAIN)) / "integrations" / "gone" / "icon.png"
    )
    assert cache_path.is_file()
    stale_time = time.time() - CACHE_TTL - 1
    os.utime(cache_path, (stale_time, stale_time))

    # Stale 404 with placeholder=no still returns 404
    resp = await client.get("/api/brands/integration/gone/icon.png?placeholder=no")
    assert resp.status == HTTPStatus.NOT_FOUND

    # Background refresh should have been triggered
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2


# ------------------------------------------------------------------
# Custom integration brand files
# ------------------------------------------------------------------


async def test_custom_integration_brand_served(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that custom integration brand files are served."""
    custom = _create_custom_integration(hass, "my_custom", has_branding=True)

    # Create the brand file on disk
    brand_dir = Path(custom.file_path) / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "icon.png").write_bytes(FAKE_PNG)

    with patch(
        "homeassistant.components.brands.async_get_custom_components",
        return_value={"my_custom": custom},
    ):
        client = await hass_client()
        resp = await client.get("/api/brands/integration/my_custom/icon.png")

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == FAKE_PNG
    # Should not have called CDN
    assert aioclient_mock.call_count == 0


async def test_custom_integration_no_brand_falls_through(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that custom integration without brand falls through to CDN."""
    custom = _create_custom_integration(hass, "my_custom", has_branding=False)

    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/my_custom/icon.png",
        content=FAKE_PNG,
    )

    with patch(
        "homeassistant.components.brands.async_get_custom_components",
        return_value={"my_custom": custom},
    ):
        client = await hass_client()
        resp = await client.get("/api/brands/integration/my_custom/icon.png")

    assert resp.status == HTTPStatus.OK
    assert aioclient_mock.call_count == 1


async def test_custom_integration_brand_missing_file_falls_through(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that custom integration with brand dir but missing file falls through."""
    custom = _create_custom_integration(hass, "my_custom", has_branding=True)

    # Create the brand directory but NOT the requested file
    brand_dir = Path(custom.file_path) / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)

    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/my_custom/icon.png",
        content=FAKE_PNG,
    )

    with patch(
        "homeassistant.components.brands.async_get_custom_components",
        return_value={"my_custom": custom},
    ):
        client = await hass_client()
        resp = await client.get("/api/brands/integration/my_custom/icon.png")

    assert resp.status == HTTPStatus.OK
    assert aioclient_mock.call_count == 1


async def test_custom_integration_takes_priority_over_cache(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that custom integration brand takes priority over disk cache."""
    custom_png = b"\x89PNGcustom"

    # Prime the CDN cache first
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/my_custom/icon.png",
        content=FAKE_PNG,
    )

    client = await hass_client()
    resp = await client.get("/api/brands/integration/my_custom/icon.png")
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == FAKE_PNG

    # Now create a custom integration with brand
    custom = _create_custom_integration(hass, "my_custom", has_branding=True)
    brand_dir = Path(custom.file_path) / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "icon.png").write_bytes(custom_png)

    with patch(
        "homeassistant.components.brands.async_get_custom_components",
        return_value={"my_custom": custom},
    ):
        resp = await client.get("/api/brands/integration/my_custom/icon.png")

    # Custom integration brand takes priority
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == custom_png


# ------------------------------------------------------------------
# Custom integration image fallback chains
# ------------------------------------------------------------------


async def test_custom_integration_logo_falls_back_to_icon(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that requesting logo.png falls back to icon.png for custom integrations."""
    custom = _create_custom_integration(hass, "my_custom", has_branding=True)
    brand_dir = Path(custom.file_path) / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "icon.png").write_bytes(FAKE_PNG)

    with patch(
        "homeassistant.components.brands.async_get_custom_components",
        return_value={"my_custom": custom},
    ):
        client = await hass_client()
        resp = await client.get("/api/brands/integration/my_custom/logo.png")

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == FAKE_PNG
    assert aioclient_mock.call_count == 0


async def test_custom_integration_dark_icon_falls_back_to_icon(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that dark_icon.png falls back to icon.png for custom integrations."""
    custom = _create_custom_integration(hass, "my_custom", has_branding=True)
    brand_dir = Path(custom.file_path) / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "icon.png").write_bytes(FAKE_PNG)

    with patch(
        "homeassistant.components.brands.async_get_custom_components",
        return_value={"my_custom": custom},
    ):
        client = await hass_client()
        resp = await client.get("/api/brands/integration/my_custom/dark_icon.png")

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == FAKE_PNG
    assert aioclient_mock.call_count == 0


async def test_custom_integration_dark_logo_falls_back_through_chain(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that dark_logo.png walks the full fallback chain."""
    custom = _create_custom_integration(hass, "my_custom", has_branding=True)
    brand_dir = Path(custom.file_path) / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)
    # Only icon.png exists; dark_logo → dark_icon → logo → icon
    (brand_dir / "icon.png").write_bytes(FAKE_PNG)

    with patch(
        "homeassistant.components.brands.async_get_custom_components",
        return_value={"my_custom": custom},
    ):
        client = await hass_client()
        resp = await client.get("/api/brands/integration/my_custom/dark_logo.png")

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == FAKE_PNG
    assert aioclient_mock.call_count == 0


async def test_custom_integration_dark_logo_prefers_dark_icon(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that dark_logo.png prefers dark_icon.png over icon.png."""
    dark_icon_data = b"\x89PNGdarkicon"
    custom = _create_custom_integration(hass, "my_custom", has_branding=True)
    brand_dir = Path(custom.file_path) / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "icon.png").write_bytes(FAKE_PNG)
    (brand_dir / "dark_icon.png").write_bytes(dark_icon_data)

    with patch(
        "homeassistant.components.brands.async_get_custom_components",
        return_value={"my_custom": custom},
    ):
        client = await hass_client()
        resp = await client.get("/api/brands/integration/my_custom/dark_logo.png")

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == dark_icon_data


async def test_custom_integration_icon2x_falls_back_to_icon(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that icon@2x.png falls back to icon.png."""
    custom = _create_custom_integration(hass, "my_custom", has_branding=True)
    brand_dir = Path(custom.file_path) / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "icon.png").write_bytes(FAKE_PNG)

    with patch(
        "homeassistant.components.brands.async_get_custom_components",
        return_value={"my_custom": custom},
    ):
        client = await hass_client()
        resp = await client.get("/api/brands/integration/my_custom/icon@2x.png")

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == FAKE_PNG
    assert aioclient_mock.call_count == 0


async def test_custom_integration_logo2x_falls_back_to_logo_then_icon(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that logo@2x.png falls back to logo.png then icon.png."""
    logo_data = b"\x89PNGlogodata"
    custom = _create_custom_integration(hass, "my_custom", has_branding=True)
    brand_dir = Path(custom.file_path) / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "icon.png").write_bytes(FAKE_PNG)
    (brand_dir / "logo.png").write_bytes(logo_data)

    with patch(
        "homeassistant.components.brands.async_get_custom_components",
        return_value={"my_custom": custom},
    ):
        client = await hass_client()
        resp = await client.get("/api/brands/integration/my_custom/logo@2x.png")

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == logo_data


async def test_custom_integration_no_fallback_match_falls_through_to_cdn(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that if no fallback image exists locally, we fall through to CDN."""
    custom = _create_custom_integration(hass, "my_custom", has_branding=True)
    brand_dir = Path(custom.file_path) / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)
    # brand dir exists but is empty - no icon.png either

    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/my_custom/icon.png",
        content=FAKE_PNG,
    )

    with patch(
        "homeassistant.components.brands.async_get_custom_components",
        return_value={"my_custom": custom},
    ):
        client = await hass_client()
        resp = await client.get("/api/brands/integration/my_custom/icon.png")

    assert resp.status == HTTPStatus.OK
    assert aioclient_mock.call_count == 1


# ------------------------------------------------------------------
# Hardware view: /api/brands/hardware/{category}/{image:.+}
# ------------------------------------------------------------------


async def test_hardware_view_serves_from_cdn(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test serving a hardware brand image from CDN."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/hardware/boards/green.png",
        content=FAKE_PNG,
    )

    client = await hass_client()
    resp = await client.get("/api/brands/hardware/boards/green.png")

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == FAKE_PNG


async def test_hardware_view_invalid_category(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that invalid category names return 404."""
    client = await hass_client()

    resp = await client.get("/api/brands/hardware/INVALID/board.png")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_hardware_view_invalid_image_extension(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that non-png image names return 404."""
    client = await hass_client()

    resp = await client.get("/api/brands/hardware/boards/image.jpg")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_hardware_view_invalid_image_characters(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that image names with invalid characters return 404."""
    client = await hass_client()

    resp = await client.get("/api/brands/hardware/boards/Bad-Name.png")
    assert resp.status == HTTPStatus.NOT_FOUND

    resp = await client.get("/api/brands/hardware/boards/../etc.png")
    assert resp.status == HTTPStatus.NOT_FOUND


# ------------------------------------------------------------------
# CDN timeout handling
# ------------------------------------------------------------------


async def test_cdn_timeout_returns_404(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that CDN timeout results in 404 with placeholder=no."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/slow/icon.png",
        exc=TimeoutError(),
    )

    client = await hass_client()
    resp = await client.get("/api/brands/integration/slow/icon.png?placeholder=no")

    assert resp.status == HTTPStatus.NOT_FOUND


# ------------------------------------------------------------------
# Authentication
# ------------------------------------------------------------------


async def test_authenticated_request(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that authenticated requests succeed."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/hue/icon.png",
        content=FAKE_PNG,
    )

    client = await hass_client()
    resp = await client.get("/api/brands/integration/hue/icon.png")

    assert resp.status == HTTPStatus.OK


async def test_token_query_param_authentication(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a valid access token in query param authenticates."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/hue/icon.png",
        content=FAKE_PNG,
    )

    token = hass.data[DOMAIN][-1]
    client = await hass_client_no_auth()
    resp = await client.get(f"/api/brands/integration/hue/icon.png?token={token}")

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == FAKE_PNG


async def test_unauthenticated_request_forbidden(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that unauthenticated requests are forbidden."""
    client = await hass_client_no_auth()

    resp = await client.get("/api/brands/integration/hue/icon.png")
    assert resp.status == HTTPStatus.FORBIDDEN

    resp = await client.get("/api/brands/hardware/boards/green.png")
    assert resp.status == HTTPStatus.FORBIDDEN


async def test_invalid_token_forbidden(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test that an invalid access token in query param is forbidden."""
    client = await hass_client_no_auth()
    resp = await client.get("/api/brands/integration/hue/icon.png?token=invalid_token")

    assert resp.status == HTTPStatus.FORBIDDEN


async def test_invalid_bearer_token_unauthorized(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test that an invalid Bearer token returns unauthorized."""
    client = await hass_client_no_auth()
    resp = await client.get(
        "/api/brands/integration/hue/icon.png",
        headers={"Authorization": "Bearer invalid_token"},
    )

    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_token_rotation(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that access tokens rotate over time."""
    aioclient_mock.get(
        f"{BRANDS_CDN_URL}/brands/hue/icon.png",
        content=FAKE_PNG,
    )

    original_token = hass.data[DOMAIN][-1]
    client = await hass_client_no_auth()

    # Original token works
    resp = await client.get(
        f"/api/brands/integration/hue/icon.png?token={original_token}"
    )
    assert resp.status == HTTPStatus.OK

    # Trigger token rotation
    freezer.tick(TOKEN_CHANGE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Deque now contains a different newest token
    new_token = hass.data[DOMAIN][-1]
    assert new_token != original_token

    # New token works
    resp = await client.get(f"/api/brands/integration/hue/icon.png?token={new_token}")
    assert resp.status == HTTPStatus.OK


# ------------------------------------------------------------------
# WebSocket API
# ------------------------------------------------------------------


async def test_ws_access_token(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the brands/access_token WebSocket command."""
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "brands/access_token"})
    resp = await client.receive_json()

    assert resp["success"]
    assert resp["result"]["token"] == hass.data[DOMAIN][-1]
