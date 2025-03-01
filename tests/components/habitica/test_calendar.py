"""Tests for the Habitica calendar platform."""

from collections.abc import Generator
from unittest.mock import patch

from freezegun.api import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def calendar_only() -> Generator[None]:
    """Enable only the calendar platform."""
    with patch(
        "homeassistant.components.habitica.PLATFORMS",
        [Platform.CALENDAR],
    ):
        yield


@pytest.fixture(autouse=True)
async def set_tz(hass: HomeAssistant) -> None:
    """Fixture to set timezone."""
    await hass.config.async_set_time_zone("Europe/Berlin")


@pytest.mark.usefixtures("habitica")
@freeze_time("2024-09-20T22:00:00.000Z")
async def test_calendar_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the Habitica calendar platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity"),
    [
        "calendar.test_user_to_do_s",
        "calendar.test_user_dailies",
        "calendar.test_user_daily_reminders",
        "calendar.test_user_to_do_reminders",
    ],
)
@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        ("2024-08-29", "2024-10-08"),
        ("2023-08-01", "2023-08-02"),
    ],
    ids=[
        "default date range",
        "date range in the past",
    ],
)
@pytest.mark.usefixtures("habitica")
async def test_api_events(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    entity: str,
    start_date: str,
    end_date: str,
) -> None:
    """Test calendar event."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client()
    response = await client.get(
        f"/api/calendars/{entity}?start={start_date}&end={end_date}"
    )

    assert await response.json() == snapshot
