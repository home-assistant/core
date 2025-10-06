"""Fixtures for the london_underground tests."""

from collections.abc import AsyncGenerator
import json
from unittest.mock import AsyncMock, patch

from london_tube_status import parse_api_response
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
        client.data = fixture_data

        yield client
