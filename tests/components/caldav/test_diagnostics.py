"""Tests for the CalDAV diagnostics."""

from unittest.mock import Mock

from caldav.lib.error import DAVError
from caldav.lib.http_sync import requests as caldav_requests
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


def _mock_calendar(name: str | None, components: list[str]) -> Mock:
    """Return a calendar with a display name and supported components."""
    calendar = Mock()
    calendar.get_display_name.return_value = name
    calendar.get_supported_components.return_value = components
    return calendar


@pytest.fixture(name="calendars")
def mock_calendars() -> list[Mock]:
    """Fixture to provide calendars returned by CalDAV client."""
    return [
        _mock_calendar("Personal", ["VTODO", "VEVENT"]),
        _mock_calendar(None, ["VTODO"]),
    ]


@pytest.mark.freeze_time("2023-06-05")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == snapshot


@pytest.mark.freeze_time("2023-06-05")
@pytest.mark.parametrize(
    "error",
    [
        caldav_requests.exceptions.ConnectionError(),
        caldav_requests.exceptions.Timeout(),
        DAVError(),
    ],
    ids=["connection_error", "timeout", "dav_error"],
)
async def test_entry_diagnostics_server_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    error: Exception,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics when the server fails to list the calendars."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    dav_client.return_value.get_principal.side_effect = error
    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == snapshot


@pytest.mark.freeze_time("2023-06-05")
async def test_entry_diagnostics_setup_failed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics are available for an entry that failed to set up."""
    dav_client.return_value.get_principal.side_effect = DAVError()
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == snapshot
