"""Test fixtures for buienradar."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from buienradar.urls import JSON_FEED_URL, json_precipitation_forecast_url
import pytest
from pytest_homeassistant.common import load_fixture
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.buienradar.const import DOMAIN

from . import TEST_LATITUDE, TEST_LONGITUDE


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.buienradar.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_buienradar_feeds(aioclient_mock: AiohttpClientMocker) -> None:
    """Serve the Buienradar weather and rain forecast feeds."""
    aioclient_mock.get(JSON_FEED_URL, text=load_fixture("feed.json", DOMAIN))
    aioclient_mock.get(
        json_precipitation_forecast_url(TEST_LATITUDE, TEST_LONGITUDE),
        text=load_fixture("rain.txt", DOMAIN),
    )
