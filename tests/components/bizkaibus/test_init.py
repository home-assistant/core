"""Tests for the Bizkaibus integration setup."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.components.bizkaibus.const import (
    CONF_LINE_IDS,
    CONF_LINES,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_creates_sensors(
    hass: HomeAssistant,
) -> None:
    """Test setting up an entry creates one sensor per selected line."""
    arrival_time = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    timetable = SimpleNamespace(
        name="Central Station",
        arrivals={
            "A": SimpleNamespace(
                line=SimpleNamespace(id="A", route="Route A"),
                nearestArrival=SimpleNamespace(GetUTC=arrival_time.isoformat),
                nextArrival=SimpleNamespace(
                    GetUTC=lambda: arrival_time.replace(minute=15).isoformat()
                ),
            ),
            "B": SimpleNamespace(
                line=SimpleNamespace(id="B", route="Route B"),
                nearestArrival=SimpleNamespace(
                    GetUTC=arrival_time.replace(minute=10).isoformat
                ),
                nextArrival=None,
            ),
        },
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STOP_ID: "1234"},
        options={
            CONF_LINE_IDS: ["A", "B"],
            CONF_LINES: {"A": "Route A", "B": "Route B"},
        },
        unique_id="1234",
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.bizkaibus.BizkaibusAPI") as mock_api_class:
        mock_api_class.return_value.GetTimetable = AsyncMock(return_value=timetable)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.get("sensor.mock_title_a_route_a").state == arrival_time.isoformat()
    )
    assert (
        hass.states.get("sensor.mock_title_b_route_b").state
        == arrival_time.replace(minute=10).isoformat()
    )
    assert hass.states.get("sensor.mock_title_a_route_a").attributes["attribution"] == (
        "Data provided by Bizkaibus."
    )
    assert hass.states.get("sensor.mock_title_a_route_a").attributes[
        "next_arrival"
    ] == (arrival_time.replace(minute=15))


async def test_setup_entry_without_lines_creates_no_sensors(
    hass: HomeAssistant,
) -> None:
    """Test setting up an entry without selected lines creates no entities."""
    timetable = SimpleNamespace(name=None, arrivals={})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STOP_ID: "1234"},
        options={CONF_LINE_IDS: [], CONF_LINES: {}},
        unique_id="1234",
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.bizkaibus.BizkaibusAPI") as mock_api_class:
        mock_api_class.return_value.GetTimetable = AsyncMock(return_value=timetable)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert not [state for state in hass.states.async_all() if state.domain == "sensor"]


async def test_unload_entry(
    hass: HomeAssistant,
) -> None:
    """Test unloading an entry removes its sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STOP_ID: "1234"},
        options={CONF_LINE_IDS: ["A"], CONF_LINES: {"A": "Route A"}},
        unique_id="1234",
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.bizkaibus.BizkaibusAPI") as mock_api_class:
        mock_api_class.return_value.GetTimetable = AsyncMock(
            return_value=SimpleNamespace(name=None, arrivals={})
        )
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state is ConfigEntryState.NOT_LOADED
