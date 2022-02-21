"""Fixtures for Sonarr integration tests."""
from collections.abc import Generator
import json
from unittest.mock import MagicMock, patch

import pytest
from sonarr.models import (
    Application,
    CommandItem,
    Episode,
    QueueItem,
    SeriesItem,
    WantedResults,
)

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


def sonarr_calendar():
    """Generate a response for the calendar method."""
    results = json.loads(load_fixture("sonarr/calendar.json"))
    return [Episode.from_dict(result) for result in results]


def sonarr_commands():
    """Generate a response for the commands method."""
    results = json.loads(load_fixture("sonarr/command.json"))
    return [CommandItem.from_dict(result) for result in results]


def sonarr_queue():
    """Generate a response for the queue method."""
    results = json.loads(load_fixture("sonarr/queue.json"))
    return [QueueItem.from_dict(result) for result in results]


def sonarr_series():
    """Generate a response for the series method."""
    results = json.loads(load_fixture("sonarr/series.json"))
    return [SeriesItem.from_dict(result) for result in results]


def sonarr_wanted():
    """Generate a response for the wanted method."""
    results = json.loads(load_fixture("sonarr/wanted-missing.json"))
    return WantedResults.from_dict(results)


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
def mock_setup_entry() -> Generator[None, None, None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.sonarr.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_sonarr_config_flow(
    request: pytest.FixtureRequest,
) -> Generator[None, MagicMock, None]:
    """Return a mocked Sonarr client."""
    fixture: str = "sonarr/app.json"
    if hasattr(request, "param") and request.param:
        fixture = request.param

    app = Application(json.loads(load_fixture(fixture)))
    with patch(
        "homeassistant.components.sonarr.config_flow.Sonarr", autospec=True
    ) as sonarr_mock:
        client = sonarr_mock.return_value
        client.host = "192.168.1.189"
        client.port = 8989
        client.base_path = "/api"
        client.tls = False
        client.app = app
        client.update.return_value = app
        client.calendar.return_value = sonarr_calendar()
        client.commands.return_value = sonarr_commands()
        client.queue.return_value = sonarr_queue()
        client.series.return_value = sonarr_series()
        client.wanted.return_value = sonarr_wanted()
        yield client


@pytest.fixture
def mock_sonarr(request: pytest.FixtureRequest) -> Generator[None, MagicMock, None]:
    """Return a mocked Sonarr client."""
    fixture: str = "sonarr/app.json"
    if hasattr(request, "param") and request.param:
        fixture = request.param

    app = Application(json.loads(load_fixture(fixture)))
    with patch("homeassistant.components.sonarr.Sonarr", autospec=True) as sonarr_mock:
        client = sonarr_mock.return_value
        client.host = "192.168.1.189"
        client.port = 8989
        client.base_path = "/api"
        client.tls = False
        client.app = app
        client.update.return_value = app
        client.calendar.return_value = sonarr_calendar()
        client.commands.return_value = sonarr_commands()
        client.queue.return_value = sonarr_queue()
        client.series.return_value = sonarr_series()
        client.wanted.return_value = sonarr_wanted()
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
