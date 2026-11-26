"""The tests for the Islamic prayer times sensor platform."""

from datetime import timedelta

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.islamic_prayer_times.const import (
    CONF_ISHA_CALENDAR_END,
    DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import NOW, PRAYER_TIMES, PRAYER_TIMES_TOMORROW, PRAYER_TIMES_YESTERDAY

CONTEXT_ENTITY_IDS = {
    key: f"sensor.islamic_prayer_times_{key}"
    for key in (
        "current_prayer",
        "current_prayer_started",
        "current_prayer_ends",
        "next_prayer",
        "next_prayer_starts",
    )
}


@pytest.fixture(autouse=True)
async def set_utc(hass: HomeAssistant) -> None:
    """Set timezone to UTC."""
    await hass.config.async_set_time_zone("UTC")


@pytest.mark.usefixtures("mock_calculator")
@pytest.mark.parametrize(
    ("key", "sensor_name"),
    [
        ("Fajr", "sensor.islamic_prayer_times_fajr_prayer"),
        ("Sunrise", "sensor.islamic_prayer_times_sunrise_time"),
        ("Dhuhr", "sensor.islamic_prayer_times_dhuhr_prayer"),
        ("Asr", "sensor.islamic_prayer_times_asr_prayer"),
        ("Maghrib", "sensor.islamic_prayer_times_maghrib_prayer"),
        ("Isha", "sensor.islamic_prayer_times_isha_prayer"),
        ("Midnight", "sensor.islamic_prayer_times_midnight_time"),
    ],
)
# In our example data, Islamic midnight occurs at 00:44
# (yesterday's times, occurs today) and 00:45 (today's times,
# occurs tomorrow), hence we check that the times roll over at
# exactly the desired minute
@pytest.mark.parametrize(
    ("offset", "prayer_times"),
    [
        (timedelta(days=-1), PRAYER_TIMES_YESTERDAY),
        (timedelta(minutes=44), PRAYER_TIMES_YESTERDAY),
        (timedelta(minutes=44, seconds=1), PRAYER_TIMES),  # Rolls over at 00:44 + 1 sec
        (timedelta(days=1, minutes=45), PRAYER_TIMES),
        (
            timedelta(days=1, minutes=45, seconds=1),  # Rolls over at 00:45 + 1 sec
            PRAYER_TIMES_TOMORROW,
        ),
    ],
)
async def test_islamic_prayer_times_sensors(
    hass: HomeAssistant,
    schedules: dict[str, dict[str, str | int | None]],
    key: str,
    sensor_name: str,
    offset: timedelta,
    prayer_times: dict[str, str],
) -> None:
    """Test minimum Islamic prayer times configuration."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    now = NOW + offset
    for day_offset, times in zip(
        (-1, 0, 1),
        (PRAYER_TIMES_YESTERDAY, PRAYER_TIMES, PRAYER_TIMES_TOMORROW),
        strict=True,
    ):
        schedules[str((now + timedelta(days=day_offset)).date())] = times.copy()
    with freeze_time(now):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(sensor_name).state == prayer_times[key]


@pytest.mark.usefixtures("prayer_entry")
@pytest.mark.parametrize(
    ("now", "current", "start", "end", "next_prayer", "next_start"),
    [
        (
            "2020-01-01T00:43:59Z",
            "isha",
            "2019-12-31T18:52:00+00:00",
            "2020-01-01T00:44:00+00:00",
            "fajr",
            "2020-01-01T06:10:00+00:00",
        ),
        (
            "2020-01-01T00:44:00Z",
            "between_prayers",
            STATE_UNAVAILABLE,
            STATE_UNAVAILABLE,
            "fajr",
            "2020-01-01T06:10:00+00:00",
        ),
        (
            "2020-01-01T06:10:00Z",
            "fajr",
            "2020-01-01T06:10:00+00:00",
            "2020-01-01T07:25:00+00:00",
            "dhuhr",
            "2020-01-01T12:30:00+00:00",
        ),
        (
            "2020-01-01T07:25:00Z",
            "between_prayers",
            STATE_UNAVAILABLE,
            STATE_UNAVAILABLE,
            "dhuhr",
            "2020-01-01T12:30:00+00:00",
        ),
        (
            "2020-01-01T12:30:00Z",
            "dhuhr",
            "2020-01-01T12:30:00+00:00",
            "2020-01-01T15:32:00+00:00",
            "asr",
            "2020-01-01T15:32:00+00:00",
        ),
        (
            "2020-01-01T15:32:00Z",
            "asr",
            "2020-01-01T15:32:00+00:00",
            "2020-01-01T17:34:00+00:00",
            "maghrib",
            "2020-01-01T17:35:00+00:00",
        ),
        (
            "2020-01-01T17:34:00Z",
            "between_prayers",
            STATE_UNAVAILABLE,
            STATE_UNAVAILABLE,
            "maghrib",
            "2020-01-01T17:35:00+00:00",
        ),
        (
            "2020-01-01T17:35:00Z",
            "maghrib",
            "2020-01-01T17:35:00+00:00",
            "2020-01-01T18:53:00+00:00",
            "isha",
            "2020-01-01T18:53:00+00:00",
        ),
        (
            "2020-01-01T18:53:00Z",
            "isha",
            "2020-01-01T18:53:00+00:00",
            "2020-01-02T00:45:00+00:00",
            "fajr",
            "2020-01-02T06:11:00+00:00",
        ),
        (
            "2020-01-02T00:45:00Z",
            "between_prayers",
            STATE_UNAVAILABLE,
            STATE_UNAVAILABLE,
            "fajr",
            "2020-01-02T06:11:00+00:00",
        ),
    ],
)
async def test_prayer_context_transitions(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    now: str,
    current: str,
    start: str,
    end: str,
    next_prayer: str,
    next_start: str,
) -> None:
    """Publish five context values at exact boundaries, including gaps and midnight."""
    freezer.move_to(now)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert {
        key: hass.states.get(entity_id).state
        for key, entity_id in CONTEXT_ENTITY_IDS.items()
    } == {
        "current_prayer": current,
        "current_prayer_started": start,
        "current_prayer_ends": end,
        "next_prayer": next_prayer,
        "next_prayer_starts": next_start,
    }
    assert (
        hass.states.get(CONTEXT_ENTITY_IDS["next_prayer_starts"]).attributes[
            "device_class"
        ]
        == "timestamp"
    )
    assert (
        hass.states.get(CONTEXT_ENTITY_IDS["current_prayer"]).attributes["device_class"]
        == "enum"
    )


@pytest.mark.parametrize(
    ("choice", "current", "end"),
    [
        ("first_third", "between_prayers", STATE_UNAVAILABLE),
        ("half_night", "isha", "2020-01-02T00:45:00+00:00"),
        ("next_fajr", "isha", "2020-01-02T06:11:00+00:00"),
    ],
)
async def test_context_isha_end_option(
    hass: HomeAssistant,
    prayer_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    choice: str,
    current: str,
    end: str,
) -> None:
    """Context sensors immediately use the same Isha option as the calendar."""
    freezer.move_to("2020-01-01T23:00:00Z")
    hass.config_entries.async_update_entry(
        prayer_entry, options={CONF_ISHA_CALENDAR_END: choice}
    )
    await hass.async_block_till_done()
    assert hass.states.get(CONTEXT_ENTITY_IDS["current_prayer"]).state == current
    assert hass.states.get(CONTEXT_ENTITY_IDS["current_prayer_ends"]).state == end
    assert (
        hass.states.get(CONTEXT_ENTITY_IDS["next_prayer_starts"]).state
        == "2020-01-02T06:11:00+00:00"
    )


async def test_context_without_calendar_or_individual_sensors(
    hass: HomeAssistant,
    prayer_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Context sensors work and transition with every other location entity disabled."""
    assert await hass.config_entries.async_unload(prayer_entry.entry_id)
    for entity in er.async_entries_for_config_entry(
        entity_registry, prayer_entry.entry_id
    ):
        if entity.entity_id not in CONTEXT_ENTITY_IDS.values():
            entity_registry.async_update_entity(
                entity.entity_id, disabled_by=er.RegistryEntryDisabler.USER
            )
    assert await hass.config_entries.async_setup(prayer_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("calendar.islamic_prayer_times") is None
    assert hass.states.get("sensor.islamic_prayer_times_fajr_prayer") is None
    freezer.move_to("2020-01-01T06:10:00Z")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(CONTEXT_ENTITY_IDS["current_prayer"]).state == "fajr"
    assert (
        hass.states.get(CONTEXT_ENTITY_IDS["current_prayer_started"]).state
        == "2020-01-01T06:10:00+00:00"
    )
    assert (
        hass.states.get(CONTEXT_ENTITY_IDS["current_prayer_ends"]).state
        == "2020-01-01T07:25:00+00:00"
    )
    assert hass.states.get(CONTEXT_ENTITY_IDS["next_prayer"]).state == "dhuhr"

    freezer.move_to("2020-01-01T07:25:00Z")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get(CONTEXT_ENTITY_IDS["current_prayer"]).state == "between_prayers"
    )
    assert (
        hass.states.get(CONTEXT_ENTITY_IDS["current_prayer_ends"]).state
        == STATE_UNAVAILABLE
    )

    freezer.move_to("2020-01-01T12:30:00Z")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(CONTEXT_ENTITY_IDS["current_prayer"]).state == "dhuhr"
    assert hass.states.get(CONTEXT_ENTITY_IDS["next_prayer"]).state == "asr"

    assert await hass.config_entries.async_unload(prayer_entry.entry_id)
    freezer.move_to("2020-01-01T15:32:00Z")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert all(
        hass.states.get(entity_id).state == STATE_UNAVAILABLE
        for entity_id in CONTEXT_ENTITY_IDS.values()
    )


@pytest.mark.usefixtures("prayer_entry")
async def test_context_unavailable_and_recovery(
    hass: HomeAssistant,
    schedules: dict[str, dict[str, str | int | None]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Invalid windows do not masquerade as between prayers, and recover on refresh."""
    schedules["2020-01-01"]["Sunset"] = "unavailable"
    freezer.move_to("2020-01-01T12:30:00Z")
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: CONTEXT_ENTITY_IDS["current_prayer"]},
        blocking=True,
    )
    assert all(
        hass.states.get(entity_id).state == STATE_UNAVAILABLE
        for entity_id in CONTEXT_ENTITY_IDS.values()
    )
    schedules["2020-01-01"]["Sunset"] = "2020-01-01T17:34:00Z"
    freezer.move_to("2020-01-01T12:31:00Z")
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: CONTEXT_ENTITY_IDS["current_prayer"]},
        blocking=True,
    )
    assert hass.states.get(CONTEXT_ENTITY_IDS["current_prayer"]).state == "dhuhr"
    assert (
        hass.states.get(CONTEXT_ENTITY_IDS["current_prayer_started"]).state
        == "2020-01-01T12:30:00+00:00"
    )
