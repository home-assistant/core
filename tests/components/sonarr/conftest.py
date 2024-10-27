"""Fixtures for Sonarr integration tests."""

from collections.abc import Generator
import json
from unittest.mock import MagicMock, patch

from aiopyarr import (
    Command,
    Diskspace,
    SonarrCalendar,
    SonarrQueue,
    SonarrSeries,
    SonarrWantedMissing,
    SystemStatus,
)
import pytest

from homeassistant.components.sonarr.const import (
    CONF_BASE_PATH,
    CONF_UPCOMING_DAYS,
    CONF_WANTED_MAX_ITEMS,
    DEFAULT_UPCOMING_DAYS,
    DEFAULT_WANTED_MAX_ITEMS,
    DOMAIN,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


def sonarr_calendar() -> list[SonarrCalendar]:
    """Generate a response for the calendar method."""
    results = json.loads(load_fixture("sonarr/calendar.json"))
    return [SonarrCalendar(result) for result in results]


def sonarr_commands() -> list[Command]:
    """Generate a response for the commands method."""
    results = json.loads(load_fixture("sonarr/command.json"))
    return [Command(result) for result in results]


def sonarr_diskspace() -> list[Diskspace]:
    """Generate a response for the diskspace method."""
    results = json.loads(load_fixture("sonarr/diskspace.json"))
    return [Diskspace(result) for result in results]


def sonarr_queue() -> SonarrQueue:
    """Generate a response for the queue method."""
    results = json.loads(load_fixture("sonarr/queue.json"))
    return SonarrQueue(results)


def sonarr_series() -> list[SonarrSeries]:
    """Generate a response for the series method."""
    results = json.loads(load_fixture("sonarr/series.json"))
    return [SonarrSeries(result) for result in results]


def sonarr_system_status() -> SystemStatus:
    """Generate a response for the system status method."""
    result = json.loads(load_fixture("sonarr/system-status.json"))
    return SystemStatus(result)


def sonarr_wanted() -> SonarrWantedMissing:
    """Generate a response for the wanted method."""
    results = json.loads(load_fixture("sonarr/wanted-missing.json"))
    return SonarrWantedMissing(results)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Sonarr",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.189",
            CONF_PORT: 8989,
            CONF_BASE_PATH: "/api",
            CONF_SSL: False,
            CONF_VERIFY_SSL: False,
            CONF_API_KEY: "MOCK_API_KEY",
            CONF_UPCOMING_DAYS: DEFAULT_UPCOMING_DAYS,
            CONF_WANTED_MAX_ITEMS: DEFAULT_WANTED_MAX_ITEMS,
        },
        options={
            CONF_UPCOMING_DAYS: DEFAULT_UPCOMING_DAYS,
            CONF_WANTED_MAX_ITEMS: DEFAULT_WANTED_MAX_ITEMS,
        },
        unique_id=None,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.sonarr.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_sonarr_config_flow() -> Generator[MagicMock]:
    """Return a mocked Sonarr client."""
    with patch(
        "homeassistant.components.sonarr.config_flow.SonarrClient", autospec=True
    ) as sonarr_mock:
        client = sonarr_mock.return_value
        client.async_get_calendar.return_value = sonarr_calendar()
        client.async_get_commands.return_value = sonarr_commands()
        client.async_get_diskspace.return_value = sonarr_diskspace()
        client.async_get_queue.return_value = sonarr_queue()
        client.async_get_series.return_value = sonarr_series()
        client.async_get_system_status.return_value = sonarr_system_status()
        client.async_get_wanted.return_value = sonarr_wanted()

        yield client


@pytest.fixture
def mock_sonarr() -> Generator[MagicMock]:
    """Return a mocked Sonarr client."""
    with patch(
        "homeassistant.components.sonarr.SonarrClient", autospec=True
    ) as sonarr_mock:
        client = sonarr_mock.return_value
        client.async_get_calendar.return_value = sonarr_calendar()
        client.async_get_commands.return_value = sonarr_commands()
        client.async_get_diskspace.return_value = sonarr_diskspace()
        client.async_get_queue.return_value = sonarr_queue()
        client.async_get_series.return_value = sonarr_series()
        client.async_get_system_status.return_value = sonarr_system_status()
        client.async_get_wanted.return_value = sonarr_wanted()

        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_sonarr: MagicMock
) -> MockConfigEntry:
    """Set up the Sonarr integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
