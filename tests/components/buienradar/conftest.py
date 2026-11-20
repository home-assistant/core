"""Test fixtures for buienradar."""

from collections.abc import Generator
import copy
from unittest.mock import AsyncMock, MagicMock, patch

from buienradar.constants import DATA, MESSAGE, SUCCESS
from buienradar.urls import JSON_FEED_URL, json_precipitation_forecast_url
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from . import TEST_DATA, TEST_LATITUDE, TEST_LONGITUDE


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.buienradar.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_buienradar_data(aioclient_mock: AiohttpClientMocker) -> Generator[MagicMock]:
    """Serve the Buienradar feeds and return parsed data for them."""
    aioclient_mock.get(JSON_FEED_URL, text="{}")
    aioclient_mock.get(
        json_precipitation_forecast_url(TEST_LATITUDE, TEST_LONGITUDE), text=""
    )
    with patch(
        "homeassistant.components.buienradar.util.parse_data",
        side_effect=lambda *args: {
            SUCCESS: True,
            MESSAGE: None,
            DATA: copy.deepcopy(TEST_DATA),
        },
    ) as mock_parse_data:
        yield mock_parse_data
