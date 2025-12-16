"""Test Volvo images."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import patch

from httpx import RequestError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.volvo.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


def _patch_update_token(self) -> None:
    """Set a deterministic token for tests."""
    self.access_tokens.clear()
    self.access_tokens.append("testtoken")


class MockResponse:
    """A mocked success response."""

    def raise_for_status(self) -> None:
        """Raise if response is not successful."""


class MockErrorResponse(MockResponse):
    """A mocked error response."""

    def raise_for_status(self) -> None:
        """Raise if response is not successful."""
        raise RequestError("error")


class MockHttpxClient:
    """A mocked version of a httpx client."""

    def __init__(self, mock_response: MockResponse = MockResponse()) -> None:
        """Initialize."""
        self.headers: dict = {}
        self.mock_response = mock_response

    async def get(self, *args: Any, **kwargs: Any) -> MockResponse:
        """Get a mocked response."""
        return self.mock_response


@pytest.mark.freeze_time("2025-10-03 12:00:00+00:00")
@pytest.mark.usefixtures("mock_api", "full_model")
@pytest.mark.parametrize(
    "full_model",
    [
        "ex30_2024",
        "xc40_electric_2024",
        "xc60_phev_2020",
        "xc90_petrol_2019",
        "xc90_phev_2024",
    ],
)
async def test_image(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test image."""
    mock_client = MockHttpxClient()

    with (
        patch("homeassistant.components.volvo.PLATFORMS", [Platform.IMAGE]),
        patch(
            "homeassistant.components.volvo.image.create_async_httpx_client",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.image.ImageEntity.async_update_token",
            _patch_update_token,
        ),
    ):
        assert await setup_integration()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_api", "full_model")
@pytest.mark.parametrize(
    "full_model",
    ["s90_diesel_2018"],
)
async def test_no_images(
    hass: HomeAssistant, setup_integration: Callable[[], Awaitable[bool]]
) -> None:
    """Test vehicle without images."""
    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.IMAGE]):
        assert await setup_integration()

    assert hass.states.async_entity_ids_count(DOMAIN) == 0


@pytest.mark.usefixtures("mock_api", "full_model")
@pytest.mark.parametrize(
    "full_model",
    ["xc40_electric_2024"],
)
async def test_image_request_error(
    hass: HomeAssistant, setup_integration: Callable[[], Awaitable[bool]]
) -> None:
    """Test image request error."""
    mock_client = MockHttpxClient(MockErrorResponse())

    with (
        patch("homeassistant.components.volvo.PLATFORMS", [Platform.IMAGE]),
        patch(
            "homeassistant.components.volvo.image.create_async_httpx_client",
            return_value=mock_client,
        ),
    ):
        assert await setup_integration()

    assert hass.states.async_entity_ids_count(DOMAIN) == 0
