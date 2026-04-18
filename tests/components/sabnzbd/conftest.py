"""Configuration for Sabnzbd tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.sabnzbd.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sabnzbd.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="sabnzbd", autouse=True)
def mock_sabnzbd() -> Generator[AsyncMock]:
    """Mock the Sabnzbd API."""
    with patch(
        "homeassistant.components.sabnzbd.helpers.SabnzbdApi", autospec=True
    ) as mock_sabnzbd:
        mock = mock_sabnzbd.return_value
        mock.return_value.check_available = True
        mock.queue = load_json_object_fixture("queue.json", DOMAIN)
        yield mock


@pytest.fixture(name="config_entry")
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a MockConfigEntry for testing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Sabnzbd",
        entry_id="01JD2YVVPBC62D620DGYNG2R8H",
        data={
            CONF_API_KEY: "edc3eee7330e4fdda04489e3fbc283d0",
            CONF_URL: "http://localhost:8080",
        },
    )
    config_entry.add_to_hass(hass)

    return config_entry


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Fixture for setting up the component."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
