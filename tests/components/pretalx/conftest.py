"""Common fixtures for the pretalx tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.pretalx.const import DOMAIN
from homeassistant.const import CONF_EVENT, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

BASE_URL = "https://pretalx.com/api/events/democon"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.pretalx.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="DemoCon",
        data={CONF_URL: "https://pretalx.com", CONF_EVENT: "democon"},
        unique_id="https://pretalx.com_democon",
        entry_id="01J000000000000000000000EV",
    )


@pytest.fixture
async def mock_pretalx(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Mock the pretalx API responses."""
    aioclient_mock.get(
        f"{BASE_URL}/",
        json=await async_load_json_object_fixture(hass, "event.json", DOMAIN),
    )
    aioclient_mock.get(
        f"{BASE_URL}/rooms/",
        json=await async_load_json_object_fixture(hass, "rooms.json", DOMAIN),
    )
    aioclient_mock.get(
        f"{BASE_URL}/submissions/",
        json=await async_load_json_object_fixture(hass, "submissions.json", DOMAIN),
    )
