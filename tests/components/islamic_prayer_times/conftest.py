"""Common fixtures for the islamic_prayer_times tests."""

from collections.abc import Generator
from datetime import date as dt_date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.islamic_prayer_times.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import MOCK_CONFIG, PRAYER_TIMES, PRAYER_TIMES_TOMORROW, PRAYER_TIMES_YESTERDAY


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.islamic_prayer_times.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def schedules() -> dict[str, dict[str, str | int | None]]:
    """Return independently dated calculator results."""
    return {
        "2019-12-31": PRAYER_TIMES_YESTERDAY.copy(),
        "2020-01-01": PRAYER_TIMES.copy(),
        "2020-01-02": PRAYER_TIMES_TOMORROW.copy(),
    }


@pytest.fixture
def mock_calculator(
    schedules: dict[str, dict[str, str | int | None]],
) -> Generator[MagicMock]:
    """Mock the calculator at the library boundary, selecting by requested date."""

    def calculate(date: str, **kwargs: object) -> MagicMock:
        if date in schedules:
            times = schedules[date].copy()
        else:
            offset = dt_date.fromisoformat(date) - dt_date(2020, 1, 1)
            times = {
                name: (datetime.fromisoformat(value) + offset).isoformat()
                for name, value in PRAYER_TIMES.items()
            }
        return MagicMock(fetch_prayer_times=MagicMock(return_value=times))

    with patch(
        "homeassistant.components.islamic_prayer_times.coordinator.PrayerTimesCalculator",
        side_effect=calculate,
    ) as mock:
        yield mock


@pytest.fixture
async def prayer_entry(
    hass: HomeAssistant,
    mock_calculator: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> MockConfigEntry:
    """Set up a location with every entity initially hidden from Assist."""
    freezer.move_to("2020-01-01T00:00:00Z")
    await hass.config.async_set_time_zone("UTC")
    assert await async_setup_component(hass, "homeassistant", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        data=MOCK_CONFIG,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        async_expose_entity(hass, "conversation", entity.entity_id, False)
    return entry
