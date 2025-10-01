"""Fixtures for the london_underground tests."""

from collections.abc import AsyncGenerator
import json
from unittest.mock import AsyncMock, patch

from london_tube_status import API_URL, parse_api_response
import pytest

from homeassistant.components.london_underground.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import async_load_fixture
from tests.conftest import AiohttpClientMocker


@pytest.fixture
def mock_setup_entry():
    """Prevent setup of integration during tests."""
    with patch(
        "homeassistant.components.london_underground.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def mock_london_underground_client(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> AsyncGenerator[AsyncMock]:
    """Mock a London Underground client."""
    with (
        patch(
            "homeassistant.components.london_underground.TubeData",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.london_underground.config_flow.TubeData",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value

        # Load the fixture text
        fixture_text = await async_load_fixture(hass, "line_status.json", DOMAIN)
        fixture_data = parse_api_response(json.loads(fixture_text))

        # Mock the aiohttp request
        aioclient_mock.get(API_URL, text=fixture_text)

        # Define async side effect: when .update() is awaited, it populates .data
        async def _update():
            client.data = fixture_data
            return client.data

        client.update = AsyncMock(side_effect=_update)
        yield client
