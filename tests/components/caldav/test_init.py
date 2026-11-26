"""Unit tests for the CalDav integration."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from functools import partial
from unittest.mock import MagicMock, Mock, patch

from caldav.lib.error import AuthorizationError, DAVError, PropfindError
from caldav.lib.http_sync import requests as caldav_requests
from caldav.lib.url import URL
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
async def mock_add_to_hass(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture to add the ConfigEntry."""
    config_entry.add_to_hass(hass)


def create_calendar(name: str, components: list[str]) -> Mock:
    """Create a calendar that supports the given components."""
    calendar = Mock()
    calendar.client = None
    calendar.url = URL(f"https://example.com/{name.lower()}/")
    calendar.search = MagicMock(return_value=[])
    calendar.get_display_name = MagicMock(return_value=name)
    calendar.get_supported_components = MagicMock(return_value=components)
    calendar.get_property = MagicMock(return_value=None)
    return calendar


@pytest.fixture(name="calendars")
def mock_calendars() -> list[Mock]:
    """Fixture to provide a calendar with events and to-do items, and a journal."""
    return [
        create_calendar("Example", ["VEVENT", "VTODO"]),
        create_calendar("Journal", ["VJOURNAL"]),
    ]


async def test_load_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading of the config entry."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    with (
        patch("homeassistant.components.caldav.DAVClient") as mock_client,
        patch.object(
            hass,
            "async_add_executor_job",
            wraps=hass.async_add_executor_job,
        ) as mock_add_executor_job,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED
    assert any(
        isinstance(call.args[0], partial) and call.args[0].func is mock_client
        for call in mock_add_executor_job.call_args_list
    )

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "expected_flows"),
    [
        (Exception(), ConfigEntryState.SETUP_ERROR, []),
        (
            caldav_requests.exceptions.ConnectionError(),
            ConfigEntryState.SETUP_RETRY,
            [],
        ),
        (caldav_requests.exceptions.Timeout(), ConfigEntryState.SETUP_RETRY, []),
        (DAVError(), ConfigEntryState.SETUP_RETRY, []),
        (
            AuthorizationError(reason="Unauthorized"),
            ConfigEntryState.SETUP_ERROR,
            ["reauth_confirm"],
        ),
        (AuthorizationError(reason="Other"), ConfigEntryState.SETUP_ERROR, []),
    ],
)
async def test_client_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
    expected_flows: list[str],
) -> None:
    """Test CalDAV client failures in setup."""

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    with patch("homeassistant.components.caldav.DAVClient") as mock_client:
        mock_client.return_value.get_principal.side_effect = side_effect
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is expected_state

    flows = hass.config_entries.flow.async_progress()
    assert [flow.get("step_id") for flow in flows] == expected_flows


@pytest.mark.parametrize("platforms", [[Platform.CALENDAR, Platform.TODO]])
async def test_calendars_listed_once(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendars: list[Mock],
) -> None:
    """Test the calendars are listed once for both platforms."""
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("calendar.example")
    assert hass.states.get("todo.example")
    principal = dav_client.return_value.get_principal.return_value
    assert principal.get_calendars.call_count == 1
    assert calendars[0].get_supported_components.call_count == 1
    assert not calendars[1].get_display_name.called


async def test_calendars_listed_in_executor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendars: list[Mock],
) -> None:
    """Test the calendars are listed outside the event loop."""

    def _get_calendars() -> list[Mock]:
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        return calendars

    principal = dav_client.return_value.get_principal.return_value
    principal.get_calendars.side_effect = _get_calendars
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED
    assert principal.get_calendars.call_count == 1


@pytest.mark.parametrize("platforms", [[Platform.CALENDAR, Platform.TODO]])
@pytest.mark.parametrize(
    "get_request",
    [
        pytest.param(lambda principal, calendar: principal.get_calendars, id="list"),
        pytest.param(lambda principal, calendar: calendar.get_display_name, id="name"),
        pytest.param(
            lambda principal, calendar: calendar.get_supported_components,
            id="components",
        ),
    ],
)
async def test_calendar_listing_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    calendars: list[Mock],
    get_request: Callable[[Mock, Mock], Mock],
) -> None:
    """Test setup is retried when the server fails to list the calendars."""
    principal = dav_client.return_value.get_principal.return_value
    failing = get_request(principal, calendars[0])
    failing.side_effect = PropfindError("503 Service Unavailable")
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.states.async_entity_ids()

    failing.side_effect = None
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("calendar.example")
    assert hass.states.get("todo.example")
