"""Tests for the Dexcom coordinator polling schedule."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pydexcom import GlucoseReading
import pytest

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import CONFIG, TEST_ACCOUNT_ID, TEST_SESSION_ID

from tests.common import MockConfigEntry, async_fire_time_changed

READING_TIME = datetime.fromisoformat("2025-04-19T16:58:33+00:00")


def _reading(reading_time: datetime) -> GlucoseReading:
    """Return a glucose reading recorded at the given time."""
    timestamp = int(reading_time.timestamp() * 1000)
    return GlucoseReading(
        {
            "WT": f"Date({timestamp})",
            "ST": f"Date({timestamp})",
            "DT": f"Date({timestamp}+0000)",
            "Value": 100,
            "Trend": "Flat",
        }
    )


@pytest.fixture
def mock_reading() -> MagicMock:
    """Patch the Dexcom client and return the reading mock."""
    with (
        patch(
            "homeassistant.components.dexcom.Dexcom.get_current_glucose_reading",
        ) as mock_get_reading,
        patch(
            "homeassistant.components.dexcom.Dexcom._get_account_id",
            return_value=TEST_ACCOUNT_ID,
        ),
        patch(
            "homeassistant.components.dexcom.Dexcom._get_session_id",
            return_value=TEST_SESSION_ID,
        ),
    ):
        yield mock_get_reading


async def _setup(hass: HomeAssistant) -> None:
    """Set up the Dexcom integration."""
    entry = MockConfigEntry(
        domain="dexcom", title="test_username", unique_id="test_username", data=CONFIG
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    """Move time forward and run due refreshes."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_poll_after_fresh_reading(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_reading: MagicMock
) -> None:
    """Test the next poll is scheduled just after the next expected reading."""
    freezer.move_to(READING_TIME + timedelta(seconds=60))
    mock_reading.return_value = _reading(READING_TIME)
    await _setup(hass)
    assert mock_reading.call_count == 1

    # Next reading expected at +5 min, polled 20 s later (260 s from now)
    await _advance(hass, freezer, 259)
    assert mock_reading.call_count == 1
    await _advance(hass, freezer, 1)
    assert mock_reading.call_count == 2


async def test_backoff_on_unchanged_reading(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_reading: MagicMock
) -> None:
    """Test polling backs off while the reading has not changed."""
    freezer.move_to(READING_TIME + timedelta(seconds=10))
    mock_reading.return_value = _reading(READING_TIME)
    await _setup(hass)

    # First poll after the expected reading time
    await _advance(hass, freezer, 310)
    assert mock_reading.call_count == 2

    # Same reading: retry once after 30 s, then the default 180 s
    for delay, calls in ((30, 3), (180, 4), (180, 5)):
        await _advance(hass, freezer, delay - 1)
        assert mock_reading.call_count == calls - 1
        await _advance(hass, freezer, 1)
        assert mock_reading.call_count == calls

    # A new reading resets the schedule to follow the reading time
    new_time = READING_TIME + timedelta(minutes=5)
    mock_reading.return_value = _reading(new_time)
    await _advance(hass, freezer, 180)
    assert mock_reading.call_count == 6
    # Now well past the next expected reading, so poll after the 30 s floor
    await _advance(hass, freezer, 30)
    assert mock_reading.call_count == 7


async def test_early_refresh_keeps_schedule(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_reading: MagicMock
) -> None:
    """Test a manual refresh before the next reading is due keeps the schedule."""
    freezer.move_to(READING_TIME + timedelta(seconds=60))
    mock_reading.return_value = _reading(READING_TIME)
    await _setup(hass)

    # Manual refresh 60 s later returns the same reading, as it is not due yet
    await _advance(hass, freezer, 60)
    await async_setup_component(hass, "homeassistant", {})
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: "sensor.test_username_glucose_value"},
        blocking=True,
    )
    assert mock_reading.call_count == 2

    # The next poll still follows the reading time (+5 min 20 s), not a retry
    await _advance(hass, freezer, 199)
    assert mock_reading.call_count == 2
    await _advance(hass, freezer, 1)
    assert mock_reading.call_count == 3


async def test_default_interval_after_failure(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_reading: MagicMock
) -> None:
    """Test a failed poll falls back to the default interval, not the 30 s retry."""
    freezer.move_to(READING_TIME + timedelta(seconds=10))
    mock_reading.return_value = _reading(READING_TIME)
    await _setup(hass)

    # Unchanged reading schedules the 30 s retry, which then fails
    await _advance(hass, freezer, 310)
    assert mock_reading.call_count == 2
    mock_reading.side_effect = ConnectionError
    await _advance(hass, freezer, 30)
    assert mock_reading.call_count == 3

    # While Dexcom is failing, poll only at the default interval
    await _advance(hass, freezer, 179)
    assert mock_reading.call_count == 3
    await _advance(hass, freezer, 1)
    assert mock_reading.call_count == 4


async def test_default_interval_without_reading(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_reading: MagicMock
) -> None:
    """Test the default interval is used when no reading is returned."""
    freezer.move_to(READING_TIME)
    mock_reading.return_value = None
    await _setup(hass)

    await _advance(hass, freezer, 179)
    assert mock_reading.call_count == 1
    await _advance(hass, freezer, 1)
    assert mock_reading.call_count == 2


async def test_minimum_interval(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_reading: MagicMock
) -> None:
    """Test polling never happens sooner than 30 s for a late new reading."""
    freezer.move_to(READING_TIME + timedelta(seconds=310))
    mock_reading.return_value = _reading(READING_TIME)
    await _setup(hass)

    await _advance(hass, freezer, 29)
    assert mock_reading.call_count == 1
    await _advance(hass, freezer, 1)
    assert mock_reading.call_count == 2
