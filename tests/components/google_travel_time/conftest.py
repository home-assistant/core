"""Fixtures for Google Maps Travel Time tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.google_travel_time.const import DEFAULT_NAME, DOMAIN
from homeassistant.core import HomeAssistant

from . import COMPUTE_ROUTES_URL, ROUTES_RESPONSE


@pytest.fixture(name="mock_config")
async def mock_config_fixture(
    hass: HomeAssistant,
    routes_mock: AiohttpClientMocker,
    data: dict[str, Any],
    options: dict[str, Any],
) -> MockConfigEntry:
    """Mock a Google Travel Time config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data=data,
        options=options,
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Bypass entry setup."""
    with patch(
        "homeassistant.components.google_travel_time.async_setup_entry",
        return_value=None,
    ):
        yield


@pytest.fixture(name="routes_mock")
def routes_mock_fixture(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock the Routes API with a valid response."""
    aioclient_mock.post(COMPUTE_ROUTES_URL, json=ROUTES_RESPONSE)
    return aioclient_mock
