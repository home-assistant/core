"""Common fixtures for the Open Home Foundation Events tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.open_home_foundation_events.const import (
    API_URL,
    DOMAIN,
    SUBENTRY_TYPE_AREA,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.open_home_foundation_events.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry with a Dublin area of 50 km."""
    return MockConfigEntry(
        title="Open Home Foundation Events",
        domain=DOMAIN,
        data={},
        subentries_data=[
            ConfigSubentryDataWithId(
                data={
                    CONF_LATITUDE: 53.3498,
                    CONF_LONGITUDE: -6.2603,
                    CONF_RADIUS: 50000,
                },
                subentry_type=SUBENTRY_TYPE_AREA,
                title="Dublin",
                subentry_id="dublin-subentry-id",
                unique_id=None,
            )
        ],
    )


@pytest.fixture
async def mock_api(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> AiohttpClientMocker:
    """Mock the events endpoint."""
    aioclient_mock.get(
        API_URL, text=await async_load_fixture(hass, "events.json", DOMAIN)
    )
    return aioclient_mock
