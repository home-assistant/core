"""Test Volvo services."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient, Request, RequestError
import pytest

from homeassistant.components.volvo.const import DOMAIN
from homeassistant.components.volvo.services import (
    SERVICE_GET_IMAGE_URL,
    SERVICE_PARAM_ENTRY,
    SERVICE_PARAM_IMAGES,
    _async_image_exists,
    _parse_exterior_image_url,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_api")
async def test_setup_services(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test setup of services."""
    assert await setup_integration()

    services = hass.services.async_services_for_domain(DOMAIN)
    assert services
    assert SERVICE_GET_IMAGE_URL in services


@pytest.mark.usefixtures("mock_api")
async def test_get_image_url_all(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if get_image_url returns all image types."""
    assert await setup_integration()

    with patch(
        "homeassistant.components.volvo.services._async_image_exists",
        new=AsyncMock(return_value=True),
    ):
        images = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_IMAGE_URL,
            {
                SERVICE_PARAM_ENTRY: mock_config_entry.entry_id,
                SERVICE_PARAM_IMAGES: [],
            },
            blocking=True,
            return_response=True,
        )

        assert images
        assert images["images"]
        assert isinstance(images["images"], list)
        assert len(images["images"]) == 9


@pytest.mark.usefixtures("mock_api")
@pytest.mark.parametrize(
    "image_type",
    [
        "exterior_back",
        "exterior_back_left",
        "exterior_back_right",
        "exterior_front",
        "exterior_front_left",
        "exterior_front_right",
        "exterior_side_left",
        "exterior_side_right",
        "interior",
    ],
)
async def test_get_image_url_selected(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_config_entry: MockConfigEntry,
    image_type: str,
) -> None:
    """Test if get_image_url returns selected image types."""
    assert await setup_integration()

    with patch(
        "homeassistant.components.volvo.services._async_image_exists",
        new=AsyncMock(return_value=True),
    ):
        images = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_IMAGE_URL,
            {
                SERVICE_PARAM_ENTRY: mock_config_entry.entry_id,
                SERVICE_PARAM_IMAGES: [image_type],
            },
            blocking=True,
            return_response=True,
        )

        assert images
        assert images["images"]
        assert isinstance(images["images"], list)
        assert len(images["images"]) == 1


async def test_async_image_exists_succeeds(hass: HomeAssistant) -> None:
    """Test _async_image_exists returns True on successful response."""
    client = AsyncMock(spec=AsyncClient)
    response = AsyncMock()
    response.raise_for_status.return_value = None
    client.get.return_value = response

    assert await _async_image_exists(client, "http://example.com/image.jpg")


async def test_async_image_exists_fails(hass: HomeAssistant) -> None:
    """Test _async_image_exists returns False on request error."""
    client = AsyncMock(spec=AsyncClient)
    client.get.side_effect = RequestError(
        "Network error", request=Request("GET", "http://example.com")
    )

    assert not await _async_image_exists(client, "http://example.com/image.jpg")


def test_parse_exterior_image_url_wizz_valid_angle() -> None:
    """Replace angle segment in wizz-hosted URL when angle is valid."""
    src = "https://wizz.images.volvocars.com/images/threeQuartersRearLeft/abc123.jpg"
    result = _parse_exterior_image_url(src, "6")
    assert result == "https://wizz.images.volvocars.com/images/rear/abc123.jpg"


def test_parse_exterior_image_url_wizz_invalid_angle() -> None:
    """Return empty string for wizz-hosted URL when angle is invalid."""
    src = "https://wizz.images.volvocars.com/images/front/xyz.jpg"
    assert _parse_exterior_image_url(src, "9") == ""


def test_parse_exterior_image_url_non_wizz_sets_angle() -> None:
    """Add angle query to non-wizz URL."""
    src = "https://images.volvocars.com/image?foo=bar&angle=1"
    result = _parse_exterior_image_url(src, "3")
    assert "angle=3" in result
