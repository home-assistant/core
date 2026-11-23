"""Test the Osmund sensors."""

from dataclasses import replace
from datetime import date, timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from osmund import OsmundAccessError, OsmundUnavailableError, PriceDay
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import CLOSED_ID, LOCATIONS, price_day

PRICE_NOW = "sensor.hjem_electricity_price_now"
DAY = date(2026, 11, 17)


@pytest.fixture(autouse=True)
def at_twenty_to_eleven(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """10:40 Danish time on a Tuesday in winter."""
    freezer.move_to("2026-11-17 09:40:00+00:00")
    return freezer


async def advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, by: timedelta
) -> None:
    """Let time pass, and every update it brings run."""
    freezer.tick(by)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Three price sensors for the location with access, and none for the other."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)

    assert not [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, init_integration.entry_id
        )
        if entry.unique_id.startswith(CLOSED_ID)
    ]


async def test_the_price_now_moves_on_the_quarter_hour_without_a_call(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    at_twenty_to_eleven: FrozenDateTimeFactory,
) -> None:
    """The day's prices are held: the next hour's price needs no call."""
    assert float(hass.states.get(PRICE_NOW).state) == pytest.approx(1.10)

    await advance(hass, at_twenty_to_eleven, timedelta(minutes=20, seconds=1))

    assert float(hass.states.get(PRICE_NOW).state) == pytest.approx(1.11)
    assert mock_client.locations.call_count == 1
    assert mock_client.prices.call_count == 1


async def test_tomorrow_is_read_from_the_afternoon(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    at_twenty_to_eleven: FrozenDateTimeFactory,
) -> None:
    """Tomorrow's prices are asked for from 13:00, and today's are not asked again."""
    await advance(hass, at_twenty_to_eleven, timedelta(hours=2))
    assert [c.args[1] for c in mock_client.prices.call_args_list] == [DAY]

    await advance(hass, at_twenty_to_eleven, timedelta(minutes=30))

    assert [c.args[1] for c in mock_client.prices.call_args_list] == [
        DAY,
        DAY + timedelta(days=1),
    ]


async def test_tomorrow_is_asked_again_until_it_is_published(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    at_twenty_to_eleven: FrozenDateTimeFactory,
) -> None:
    """Until tomorrow is published, the API answers with an incomplete day."""
    priced = mock_client.prices.side_effect

    def not_published(location_id: str, day: date, resolution: str) -> PriceDay:
        if day > DAY:
            return replace(
                priced(location_id, day, resolution), complete=False, intervals=()
            )
        return priced(location_id, day, resolution)

    mock_client.prices.side_effect = not_published

    await advance(hass, at_twenty_to_eleven, timedelta(hours=2, minutes=30))
    await advance(hass, at_twenty_to_eleven, timedelta(minutes=30))

    assert [c.args[1] for c in mock_client.prices.call_args_list] == [
        DAY,
        DAY + timedelta(days=1),
        DAY + timedelta(days=1),
    ]
    assert float(hass.states.get(PRICE_NOW).state) == pytest.approx(1.13)


async def test_a_price_that_is_not_there_is_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """A day without the current interval leaves the price unknown, not unavailable."""
    whole = price_day(DAY)
    mock_client.prices.side_effect = None
    mock_client.prices.return_value = replace(
        whole, intervals=tuple(i for i in whole.intervals if i.start.hour < 10)
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(PRICE_NOW).state == STATE_UNKNOWN


async def test_a_busy_api_is_asked_again_when_it_says(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    at_twenty_to_eleven: FrozenDateTimeFactory,
) -> None:
    """The calls are shared with the customer's other tools: after a 429, wait as it says."""
    mock_client.locations.side_effect = OsmundUnavailableError("Too many requests", 60)

    await advance(hass, at_twenty_to_eleven, timedelta(minutes=30))

    assert hass.states.get(PRICE_NOW).state == STATE_UNAVAILABLE

    mock_client.locations.side_effect = None
    await advance(hass, at_twenty_to_eleven, timedelta(seconds=61))

    assert float(hass.states.get(PRICE_NOW).state) == pytest.approx(1.11)


async def test_a_location_that_loses_its_access(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    at_twenty_to_eleven: FrozenDateTimeFactory,
) -> None:
    """A location that loses its access between two calls shows no price."""
    mock_client.prices.side_effect = OsmundAccessError("Closed")

    # From 13:00, tomorrow's prices are asked for, and refused.
    await advance(hass, at_twenty_to_eleven, timedelta(hours=3))

    assert hass.states.get(PRICE_NOW).state == STATE_UNAVAILABLE


async def test_a_meter_that_measures_quarter_hours_gets_quarter_hour_prices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """A meter that measures quarter hours is billed by the quarter hour."""
    mock_client.locations.return_value = [
        replace(LOCATIONS[0], meter_resolution="PT15M"),
        LOCATIONS[1],
    ]
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert [c.args[2] for c in mock_client.prices.call_args_list] == ["PT15M"]


async def test_the_days_prices_and_when_they_are_lowest_and_highest(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The hour h costs 1 + h / 100: cheapest at midnight, most expensive at 23:00."""
    states = {
        key: hass.states.get(f"sensor.hjem_{key}").state
        for key in (
            "next_electricity_price",
            "lowest_electricity_price_today",
            "highest_electricity_price_today",
            "average_electricity_price_today",
            "time_of_lowest_electricity_price_today",
            "time_of_highest_electricity_price_today",
        )
    }

    assert float(states["next_electricity_price"]) == pytest.approx(1.11)
    assert float(states["lowest_electricity_price_today"]) == pytest.approx(1.00)
    assert float(states["highest_electricity_price_today"]) == pytest.approx(1.23)
    assert float(states["average_electricity_price_today"]) == pytest.approx(1.115)
    assert (
        states["time_of_lowest_electricity_price_today"] == "2026-11-16T23:00:00+00:00"
    )
    assert (
        states["time_of_highest_electricity_price_today"] == "2026-11-17T22:00:00+00:00"
    )


async def test_the_next_price_after_23_is_tomorrows_first(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    at_twenty_to_eleven: FrozenDateTimeFactory,
) -> None:
    """Tomorrow's prices are held from the afternoon, so the last hour has a next price."""
    await advance(hass, at_twenty_to_eleven, timedelta(hours=12, minutes=40))

    assert float(
        hass.states.get("sensor.hjem_next_electricity_price").state
    ) == pytest.approx(1.00)


async def test_without_tomorrow_the_last_hour_has_no_next_price(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    at_twenty_to_eleven: FrozenDateTimeFactory,
) -> None:
    """When tomorrow is not published, the next price after 23:00 is unknown."""
    priced = mock_client.prices.side_effect

    def not_published(location_id: str, day: date, resolution: str) -> PriceDay:
        if day > DAY:
            return replace(
                priced(location_id, day, resolution), complete=False, intervals=()
            )
        return priced(location_id, day, resolution)

    mock_client.prices.side_effect = not_published

    await advance(hass, at_twenty_to_eleven, timedelta(hours=12, minutes=40))

    assert hass.states.get("sensor.hjem_next_electricity_price").state == STATE_UNKNOWN

    # Past midnight, the new day has no prices yet: its average is unknown too.
    await advance(hass, at_twenty_to_eleven, timedelta(minutes=41))

    assert (
        hass.states.get("sensor.hjem_average_electricity_price_today").state
        == STATE_UNKNOWN
    )
