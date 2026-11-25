"""Tests for the calculated prayer calendar."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.islamic_prayer_times.const import (
    CONF_CALC_METHOD,
    CONF_ISHA_CALENDAR_END,
    CONF_LAT_ADJ_METHOD,
    CONF_MIDNIGHT_MODE,
    CONF_SCHOOL,
    DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, llm
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import MOCK_CONFIG

ENTITY_ID = "calendar.islamic_prayer_times"


async def get_events(hass: HomeAssistant, start: str, end: str) -> list[dict[str, str]]:
    """Read events through the normal calendar action."""
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "start_date_time": start,
            "end_date_time": end,
        },
        blocking=True,
        return_response=True,
    )
    assert response is not None
    return response[ENTITY_ID]["events"]


@pytest.mark.usefixtures("prayer_entry")
async def test_day_schedule(hass: HomeAssistant) -> None:
    """Expose actual windows, including an Isha that started the previous day."""
    events = await get_events(hass, "2020-01-01T00:00:00Z", "2020-01-02T00:00:00Z")
    assert [(e["summary"], e["start"], e["end"]) for e in events] == [
        ("Isha", "2019-12-31T18:52:00+00:00", "2020-01-01T00:44:00+00:00"),
        ("Fajr", "2020-01-01T06:10:00+00:00", "2020-01-01T07:25:00+00:00"),
        ("Dhuhr", "2020-01-01T12:30:00+00:00", "2020-01-01T15:32:00+00:00"),
        ("Asr", "2020-01-01T15:32:00+00:00", "2020-01-01T17:34:00+00:00"),
        ("Maghrib", "2020-01-01T17:35:00+00:00", "2020-01-01T18:53:00+00:00"),
        ("Isha", "2020-01-01T18:53:00+00:00", "2020-01-02T00:45:00+00:00"),
    ]
    assert hass.states.get(ENTITY_ID).attributes.get("supported_features", 0) == 0


@pytest.mark.parametrize(
    ("choice", "end"),
    [
        ("first_third", "2020-01-01T22:21:00+00:00"),
        ("half_night", "2020-01-02T00:45:00+00:00"),
        ("next_fajr", "2020-01-02T06:11:00+00:00"),
    ],
)
async def test_isha_end_option(
    hass: HomeAssistant,
    prayer_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    choice: str,
    end: str,
) -> None:
    """Options update cached state and queries without changing sensor times."""
    freezer.move_to("2020-01-01T19:00:00Z")
    await hass.services.async_call(
        "homeassistant", "update_entity", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    sensors = {
        state.entity_id: state.state
        for state in hass.states.async_all("sensor")
        if not state.entity_id.startswith(
            (
                "sensor.islamic_prayer_times_current_",
                "sensor.islamic_prayer_times_next_",
            )
        )
    }
    result = await hass.config_entries.options.async_init(prayer_entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_ISHA_CALENDAR_END: choice}
    )
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    events = await get_events(hass, "2020-01-01T19:00:00Z", "2020-01-01T20:00:00Z")
    assert events == [
        {
            "summary": "Isha",
            "start": "2020-01-01T18:53:00+00:00",
            "end": end,
        }
    ]
    assert hass.states.get(ENTITY_ID).attributes["end_time"] == (
        dt_util.parse_datetime(end).strftime("%Y-%m-%d %H:%M:%S")
    )
    assert {
        entity_id: hass.states.get(entity_id).state for entity_id in sensors
    } == sensors
    assert (
        hass.states.get("sensor.islamic_prayer_times_current_prayer_ends").state == end
    )


async def test_disabled_sensors(
    hass: HomeAssistant,
    prayer_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A calendar works with every timestamp sensor disabled, even after setup."""
    assert await hass.config_entries.async_unload(prayer_entry.entry_id)
    sensor_ids = [
        entity.entity_id
        for entity in er.async_entries_for_config_entry(
            entity_registry, prayer_entry.entry_id
        )
        if entity.domain == "sensor"
    ]
    assert sensor_ids
    for entity_id in sensor_ids:
        entity_registry.async_update_entity(
            entity_id, disabled_by=er.RegistryEntryDisabler.USER
        )
    assert await hass.config_entries.async_setup(prayer_entry.entry_id)
    await hass.async_block_till_done()
    assert all(hass.states.get(entity_id) is None for entity_id in sensor_ids)
    assert hass.states.get(ENTITY_ID).state == "on"
    events = await get_events(hass, "2020-01-01T00:00:00Z", "2020-01-02T00:00:00Z")
    assert [event["summary"] for event in events] == [
        "Isha",
        "Fajr",
        "Dhuhr",
        "Asr",
        "Maghrib",
        "Isha",
    ]
    assert events[1]["end"] == "2020-01-01T07:25:00+00:00"
    assert events[-1]["end"] == "2020-01-02T00:45:00+00:00"


@pytest.mark.usefixtures("prayer_entry")
@pytest.mark.parametrize(
    ("start", "end", "names"),
    [
        pytest.param(
            "2020-01-01T07:25:00Z", "2020-01-01T12:30:00Z", [], id="sunrise-gap"
        ),
        pytest.param(
            "2020-01-01T17:34:00Z", "2020-01-01T17:35:00Z", [], id="sunset-gap"
        ),
        pytest.param(
            "2020-01-01T06:10:00Z",
            "2020-01-01T06:10:01Z",
            ["Fajr"],
            id="start-inclusive",
        ),
        pytest.param(
            "2020-01-01T23:00:00Z", "2020-01-02T06:11:00Z", ["Isha"], id="end-exclusive"
        ),
        pytest.param(
            "2020-01-02T06:10:00Z",
            "2020-01-02T06:12:00Z",
            ["Fajr"],
            id="actual-next-day",
        ),
    ],
)
async def test_query_boundaries(
    hass: HomeAssistant, start: str, end: str, names: list[str]
) -> None:
    """Only return overlapping windows; never shift today's Fajr by 24 hours."""
    events = await get_events(hass, start, end)
    assert [event["summary"] for event in events] == names


@pytest.mark.usefixtures("prayer_entry")
@pytest.mark.parametrize(
    ("now", "state", "prayer"),
    [
        ("2020-01-01T00:43:59Z", "on", "Isha"),
        ("2020-01-01T00:44:00Z", "off", "Fajr"),
        ("2020-01-01T06:10:00Z", "on", "Fajr"),
        ("2020-01-01T07:25:00Z", "off", "Dhuhr"),
        ("2020-01-01T12:30:00Z", "on", "Dhuhr"),
        ("2020-01-01T15:32:00Z", "on", "Asr"),
        ("2020-01-01T17:34:00Z", "off", "Maghrib"),
        ("2020-01-01T17:35:00Z", "on", "Maghrib"),
        ("2020-01-01T18:53:00Z", "on", "Isha"),
        ("2020-01-02T00:45:00Z", "off", "Fajr"),
    ],
)
async def test_state_transitions(
    hass: HomeAssistant, now: str, state: str, prayer: str
) -> None:
    """The base calendar updates at prayer starts and ends without polling."""
    with freeze_time(now):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    result = hass.states.get(ENTITY_ID)
    assert result.state == state
    assert result.attributes["message"] == prayer


@pytest.mark.usefixtures("prayer_entry")
@pytest.mark.parametrize("midnight", ["2020-01-01T23:00:00Z", "2020-01-02T01:00:00Z"])
async def test_configured_midnight(
    hass: HomeAssistant,
    schedules: dict[str, dict[str, str | int | None]],
    midnight: str,
) -> None:
    """Isha ends at configured Islamic Midnight, before or after civil midnight."""
    schedules["2020-01-01"]["Midnight"] = midnight
    events = await get_events(hass, "2020-01-01T18:00:00Z", "2020-01-02T02:00:00Z")
    assert events[-1]["summary"] == "Isha"
    assert events[-1]["end"] == dt_util.parse_datetime(midnight).isoformat()


@pytest.mark.usefixtures("prayer_entry")
@pytest.mark.parametrize("midnight", ["23:00:00", "23:55:00"])
async def test_isha_until_next_fajr(
    hass: HomeAssistant,
    schedules: dict[str, dict[str, str | int | None]],
    freezer: FrozenDateTimeFactory,
    midnight: str,
) -> None:
    """Use the next calculation date's Fajr when Midnight cannot end Isha."""
    schedules["2020-01-01"].update(
        {"Isha": "2020-01-01T23:55:00Z", "Midnight": f"2020-01-01T{midnight}Z"}
    )
    freezer.move_to("2020-01-01T23:55:00Z")
    await hass.services.async_call(
        "homeassistant", "update_entity", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == "on"
    assert hass.states.get(ENTITY_ID).attributes["message"] == "Isha"

    events = await get_events(hass, "2020-01-01T23:55:00Z", "2020-01-02T06:11:00Z")
    assert events == [
        {
            "summary": "Isha",
            "start": "2020-01-01T23:55:00+00:00",
            "end": "2020-01-02T06:11:00+00:00",
        }
    ]

    # Today's Fajr plus 24 hours would incorrectly end Isha a minute early.
    freezer.move_to("2020-01-02T06:10:30Z")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "on"
    assert hass.states.get(ENTITY_ID).attributes["message"] == "Isha"

    freezer.move_to("2020-01-02T06:11:00Z")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "on"
    assert hass.states.get(ENTITY_ID).attributes["message"] == "Fajr"
    assert await get_events(hass, "2020-01-02T06:11:00Z", "2020-01-02T06:11:01Z") == [
        {
            "summary": "Fajr",
            "start": "2020-01-02T06:11:00+00:00",
            "end": "2020-01-02T07:26:00+00:00",
        }
    ]


@pytest.mark.usefixtures("prayer_entry")
@pytest.mark.parametrize(
    ("isha", "end"),
    [
        pytest.param("06:11:00", "06:21:00", id="fajr-equals-isha"),
        pytest.param("06:12:00", "06:22:00", id="fajr-before-isha"),
    ],
)
async def test_isha_marker_overlaps_fajr(
    hass: HomeAssistant,
    schedules: dict[str, dict[str, str | int | None]],
    isha: str,
    end: str,
) -> None:
    """Keep a labelled ten-minute Isha marker without moving the actual Fajr."""
    schedules["2020-01-01"]["Isha"] = f"2020-01-02T{isha}Z"
    events = await get_events(hass, "2020-01-02T06:12:00Z", "2020-01-02T06:13:00Z")
    assert sorted(events, key=lambda event: event["summary"]) == [
        {
            "summary": "Fajr",
            "start": "2020-01-02T06:11:00+00:00",
            "end": "2020-01-02T07:26:00+00:00",
        },
        {
            "summary": "Isha",
            "start": f"2020-01-02T{isha}+00:00",
            "end": f"2020-01-02T{end}+00:00",
            "description": "Isha start marker (10-minute display duration).",
        },
    ]
    assert [
        event["summary"]
        for event in await get_events(
            hass, f"2020-01-02T{end}Z", "2020-01-02T06:23:00Z"
        )
    ] == ["Fajr"]


@pytest.mark.usefixtures("prayer_entry")
@pytest.mark.parametrize(
    ("day", "name", "value", "midnight", "start", "end"),
    [
        (
            "2019-12-31",
            "Isha",
            "2020-01-01T01:10:00Z",
            "2020-01-01T02:00:00Z",
            "2020-01-01T01:00:00Z",
            "2020-01-01T01:30:00Z",
        ),
        (
            "2020-01-01",
            "Fajr",
            "2019-12-31T23:50:00Z",
            "2019-12-31T23:45:00Z",
            "2019-12-31T23:45:00Z",
            "2020-01-01T00:00:00Z",
        ),
    ],
)
async def test_cross_date_events(
    hass: HomeAssistant,
    schedules: dict[str, dict[str, str | int | None]],
    day: str,
    name: str,
    value: str,
    midnight: str,
    start: str,
    end: str,
) -> None:
    """Pad calculation dates to include windows crossing the requested day."""
    schedules[day][name] = value
    schedules["2019-12-31"]["Midnight"] = midnight
    events = await get_events(hass, start, end)
    assert (name, dt_util.parse_datetime(value).isoformat()) in [
        (event["summary"], event["start"]) for event in events
    ]


@pytest.mark.usefixtures("prayer_entry")
@pytest.mark.parametrize(
    "invalid",
    [
        None,
        123,
        "unavailable",
        "2020-01-01T06:10:00",
        "2020-02-31T06:10:00Z",
        "2020-01-01T15:00:00Z",
        "2020-01-01T15:32:00Z",
        "2020-01-01T18:00:00Z",
    ],
)
async def test_invalid_calculation(
    hass: HomeAssistant,
    schedules: dict[str, dict[str, str | int | None]],
    invalid: str | int | None,
) -> None:
    """Missing, naive, malformed, and inverted times fail instead of fabricating events."""
    schedules["2020-01-01"]["Sunset"] = invalid
    with pytest.raises(
        HomeAssistantError, match="Prayer times could not be calculated"
    ):
        await get_events(hass, "2020-01-01T00:00:00Z", "2020-01-02T00:00:00Z")


@pytest.mark.usefixtures("prayer_entry")
async def test_calculation_failure(
    hass: HomeAssistant, mock_calculator: MagicMock
) -> None:
    """Do not present a failed range query as an empty calendar."""
    mock_calculator.side_effect = ValueError("cannot calculate")
    with pytest.raises(
        HomeAssistantError, match="Prayer times could not be calculated"
    ):
        await get_events(hass, "2020-01-01T00:00:00Z", "2020-01-02T00:00:00Z")


@pytest.mark.usefixtures("prayer_entry")
async def test_unavailable_and_recovery(
    hass: HomeAssistant,
    schedules: dict[str, dict[str, str | int | None]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """An invalid current schedule is unavailable and recovers on a valid update."""
    schedules["2020-01-01"]["Sunset"] = "unavailable"
    freezer.move_to("2020-01-01T12:00:00Z")
    await hass.services.async_call(
        "homeassistant", "update_entity", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    schedules["2020-01-01"]["Sunset"] = "2020-01-01T17:34:00Z"
    freezer.move_to("2020-01-01T12:01:00Z")
    await hass.services.async_call(
        "homeassistant", "update_entity", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == "off"
    assert hass.states.get(ENTITY_ID).attributes["message"] == "Dhuhr"


async def test_assist_exposure(
    hass: HomeAssistant,
    prayer_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Use the standard calendar tool and exposure, keeping sensors hidden."""
    assert await async_setup_component(hass, "llm", {})
    context = llm.LLMContext(
        platform="test",
        context=Context(),
        language="en",
        assistant="conversation",
        device_id=None,
    )
    tools = await llm_component.async_get_tools(hass, context, llm.LLM_API_ASSIST)
    assert "calendar__get_events" not in [tool.name for tool in tools.tools]
    async_expose_entity(hass, "conversation", ENTITY_ID, True)
    tools = await llm_component.async_get_tools(hass, context, llm.LLM_API_ASSIST)
    assert not any(
        tool.name.startswith("islamic_prayer_times__") for tool in tools.tools
    )
    state = hass.states.get(ENTITY_ID)
    tool_input = llm.ToolInput(
        "calendar__get_events", {"calendar": state.name, "range": "today"}
    )
    api = await llm.async_get_api(hass, llm.LLM_API_ASSIST, context)
    with freeze_time("2020-01-01T13:00:00Z"):
        result = await api.async_call_tool(tool_input)
    assert not result.error
    assert [e["summary"] for e in result.data["events"]] == [
        "Dhuhr",
        "Asr",
        "Maghrib",
        "Isha",
    ]
    assert all(
        not async_should_expose(hass, "conversation", entity.entity_id)
        for entity in er.async_entries_for_config_entry(
            entity_registry, prayer_entry.entry_id
        )
        if entity.domain == "sensor"
    )
    async_expose_entity(hass, "conversation", ENTITY_ID, False)
    result = await api.async_call_tool(tool_input)
    assert result.error


async def test_multiple_locations(
    hass: HomeAssistant,
    prayer_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Each location has its own calendar and exposure choice."""
    other = MockConfigEntry(
        domain=DOMAIN,
        title="Other",
        data={**MOCK_CONFIG, "latitude": 45.0},
        minor_version=2,
    )
    other.add_to_hass(hass)
    with freeze_time("2020-01-01T12:00:00Z"):
        assert await hass.config_entries.async_setup(other.entry_id)
        await hass.async_block_till_done()
    calendar = next(
        e
        for e in er.async_entries_for_config_entry(entity_registry, other.entry_id)
        if e.domain == "calendar"
    )
    assert calendar.entity_id != ENTITY_ID
    assert calendar.unique_id != entity_registry.async_get(ENTITY_ID).unique_id
    async_expose_entity(hass, "conversation", ENTITY_ID, True)
    async_expose_entity(hass, "conversation", calendar.entity_id, False)
    assert async_should_expose(hass, "conversation", ENTITY_ID)
    assert not async_should_expose(hass, "conversation", calendar.entity_id)
    assert await hass.config_entries.async_unload(other.entry_id)
    assert hass.states.get(calendar.entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("start", "end", "school", "mode", "fajr", "asr", "midnight"),
    [
        pytest.param(
            "2020-03-08T00:00:00-05:00",
            "2020-03-09T00:00:00-04:00",
            "shafi",
            "standard",
            "2020-03-08T10:03:00+00:00",
            "2020-03-08T20:22:00+00:00",
            "2020-03-09T05:07:00+00:00",
            id="spring-forward-shafi-standard",
        ),
        pytest.param(
            "2020-11-01T00:00:00-04:00",
            "2020-11-02T00:00:00-05:00",
            "hanafi",
            "jafari",
            "2020-11-01T10:10:00+00:00",
            "2020-11-01T20:10:00+00:00",
            "2020-11-02T04:01:00+00:00",
            id="fall-back-hanafi-jafari",
        ),
    ],
)
async def test_real_calculator(
    hass: HomeAssistant,
    start: str,
    end: str,
    school: str,
    mode: str,
    fajr: str,
    asr: str,
    midnight: str,
) -> None:
    """Calculate a 23/25-hour local day with actual location and method settings."""
    await hass.config.async_set_time_zone("America/New_York")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"latitude": 40.7128, "longitude": -74.006},
        options={
            CONF_CALC_METHOD: "isna",
            CONF_SCHOOL: school,
            CONF_MIDNIGHT_MODE: mode,
        },
        minor_version=2,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    events = await get_events(hass, start, end)
    assert [event["summary"] for event in events] == [
        "Isha",
        "Fajr",
        "Dhuhr",
        "Asr",
        "Maghrib",
        "Isha",
    ]
    assert events[1]["start"] == fajr
    assert events[2]["end"] == asr
    assert events[3]["start"] == asr
    assert events[3]["end"] == events[4]["start"]
    assert events[4]["end"] == events[5]["start"]
    assert events[5]["end"] == midnight


@pytest.mark.parametrize(
    (
        "latitude",
        "longitude",
        "mode",
        "latitude_adjustment",
        "fajr",
        "isha",
        "current_prayer",
        "isha_events",
    ),
    [
        pytest.param(
            59.9139,
            10.7522,
            "standard",
            "one_seventh",
            "2026-06-21T01:10:00+00:00",
            "2026-06-21T21:28:00+00:00",
            "Asr",
            [
                {
                    "summary": "Isha",
                    "start": "2026-06-21T21:28:00+00:00",
                    "end": "2026-06-21T23:19:00+00:00",
                }
            ],
            id="oslo-one-seventh-distinct-windows",
        ),
        pytest.param(
            52.8737,
            -118.0814,
            "standard",
            "angle_based",
            "2026-06-21T09:41:00+00:00",
            "2026-06-22T06:08:00+00:00",
            "Dhuhr",
            [
                {
                    "summary": "Isha",
                    "start": "2026-06-22T06:08:00+00:00",
                    "end": "2026-06-22T07:54:00+00:00",
                }
            ],
            id="jasper-angle-based-distinct-windows",
        ),
        pytest.param(
            59.9139,
            10.7522,
            "standard",
            "middle_of_the_night",
            "2026-06-20T23:19:00+00:00",
            "2026-06-21T23:19:00+00:00",
            "Asr",
            [
                {
                    "summary": "Isha",
                    "start": "2026-06-21T23:19:00+00:00",
                    "end": "2026-06-21T23:29:00+00:00",
                    "description": "Isha start marker (10-minute display duration).",
                }
            ],
            id="oslo-isha-at-midnight",
        ),
        pytest.param(
            51.5074,
            -0.1278,
            "jafari",
            "middle_of_the_night",
            "2026-06-21T00:16:00+00:00",
            "2026-06-21T23:49:00+00:00",
            "Asr",
            [
                {
                    "summary": "Isha",
                    "start": "2026-06-21T23:49:00+00:00",
                    "end": "2026-06-22T00:16:00+00:00",
                }
            ],
            id="london-isha-after-midnight",
        ),
        pytest.param(
            52.8737,
            -118.0814,
            "standard",
            "middle_of_the_night",
            "2026-06-21T07:54:00+00:00",
            "2026-06-22T07:54:00+00:00",
            "Dhuhr",
            [
                {
                    "summary": "Isha",
                    "start": "2026-06-22T07:54:00+00:00",
                    "end": "2026-06-22T08:04:00+00:00",
                    "description": "Isha start marker (10-minute display duration).",
                }
            ],
            id="jasper-isha-at-next-date-midnight",
        ),
    ],
)
async def test_high_latitude_prayer_windows(
    hass: HomeAssistant,
    latitude: float,
    longitude: float,
    mode: str,
    latitude_adjustment: str,
    fajr: str,
    isha: str,
    current_prayer: str,
    isha_events: list[dict[str, str]],
) -> None:
    """Respect selected latitude adjustments, including distinct and collapsed windows."""
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.config.async_set_time_zone("UTC")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"latitude": latitude, "longitude": longitude},
        options={
            CONF_CALC_METHOD: "isna",
            CONF_MIDNIGHT_MODE: mode,
            CONF_LAT_ADJ_METHOD: latitude_adjustment,
        },
        minor_version=2,
    )
    entry.add_to_hass(hass)
    now = dt_util.parse_datetime("2026-06-21T20:00:00Z")
    # Freeze clock reads without replacing the date class used by the calculator.
    with (
        patch("homeassistant.util.dt.now", return_value=now),
        patch("homeassistant.util.dt.utcnow", return_value=now),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        state = hass.states.get(ENTITY_ID)
        assert state.state == "on"
        assert state.attributes["message"] == current_prayer

        events = await get_events(hass, fajr, isha)
        day_events = [event for event in events if event["summary"] != "Isha"]
        assert [event["summary"] for event in day_events] == [
            "Fajr",
            "Dhuhr",
            "Asr",
            "Maghrib",
        ]
        assert day_events[0]["start"] == fajr
        assert day_events[-1]["end"] == isha
        assert all(event["end"] > event["start"] for event in events)

        isha_time = dt_util.parse_datetime(isha)
        events = await get_events(
            hass,
            (isha_time - timedelta(seconds=1)).isoformat(),
            (isha_time + timedelta(seconds=1)).isoformat(),
        )
        assert [event for event in events if event["summary"] == "Isha"] == isha_events

    with (
        patch("homeassistant.util.dt.now", return_value=isha_time),
        patch("homeassistant.util.dt.utcnow", return_value=isha_time),
    ):
        await hass.services.async_call(
            "homeassistant", "update_entity", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
        assert (
            hass.states.get("sensor.islamic_prayer_times_current_prayer").state
            == "isha"
        )
        assert (
            hass.states.get("sensor.islamic_prayer_times_current_prayer_started").state
            == isha
        )
        assert (
            hass.states.get("sensor.islamic_prayer_times_current_prayer_ends").state
            == isha_events[0]["end"]
        )
        assert hass.states.get(ENTITY_ID).attributes["message"] == "Isha"


@pytest.mark.parametrize(
    "time_zone",
    ["Pacific/Kiritimati", "Etc/GMT+12", "America/New_York"],
)
@pytest.mark.parametrize(
    ("latitude", "longitude", "isha", "end", "fajr", "sunrise"),
    [
        pytest.param(
            21.3099,
            -157.8581,
            "2025-12-31T05:06:00+00:00",
            "2025-12-31T10:34:00+00:00",
            "2025-12-31T16:03:00+00:00",
            "2025-12-31T17:09:00+00:00",
            id="honolulu-previous-calculation-date",
        ),
        pytest.param(
            -41.2866,
            174.7756,
            "2025-12-31T09:38:00+00:00",
            "2025-12-31T12:24:00+00:00",
            "2025-12-31T15:11:00+00:00",
            "2025-12-31T16:51:00+00:00",
            id="wellington-next-calculation-date",
        ),
    ],
)
async def test_remote_location_time_zones(
    hass: HomeAssistant,
    time_zone: str,
    latitude: float,
    longitude: float,
    isha: str,
    end: str,
    fajr: str,
    sunrise: str,
) -> None:
    """Calendar queries and current/next state depend on instants, not HA's date."""
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.config.async_set_time_zone(time_zone)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"latitude": latitude, "longitude": longitude},
        minor_version=2,
    )
    entry.add_to_hass(hass)
    now = dt_util.parse_datetime("2025-12-31T10:00:00+00:00")
    with (
        patch(
            "homeassistant.util.dt.now", return_value=dt_util.as_local(now)
        ) as local_clock,
        patch("homeassistant.util.dt.utcnow", return_value=now) as utc_clock,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # Query the same physical interval expressed in each HA timezone.
        events = await get_events(
            hass,
            dt_util.as_local(now).isoformat(),
            dt_util.as_local(now + timedelta(minutes=15)).isoformat(),
        )
        assert events == [{"summary": "Isha", "start": isha, "end": end}]
        assert hass.states.get(ENTITY_ID).state == "on"
        assert hass.states.get(ENTITY_ID).attributes["message"] == "Isha"
        assert (
            hass.states.get("sensor.islamic_prayer_times_current_prayer").state
            == "isha"
        )
        assert (
            hass.states.get("sensor.islamic_prayer_times_current_prayer_started").state
            == isha
        )
        assert (
            hass.states.get("sensor.islamic_prayer_times_current_prayer_ends").state
            == end
        )
        assert (
            hass.states.get("sensor.islamic_prayer_times_next_prayer").state == "fajr"
        )
        assert (
            hass.states.get("sensor.islamic_prayer_times_next_prayer_starts").state
            == fajr
        )

        now = dt_util.parse_datetime(end)
        local_clock.return_value = dt_util.as_local(now)
        utc_clock.return_value = now
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == "off"
        assert (
            hass.states.get("sensor.islamic_prayer_times_current_prayer").state
            == "between_prayers"
        )
        assert (
            hass.states.get("sensor.islamic_prayer_times_current_prayer_ends").state
            == STATE_UNAVAILABLE
        )
        assert (
            hass.states.get("sensor.islamic_prayer_times_next_prayer_starts").state
            == fajr
        )

        now = dt_util.parse_datetime(fajr)
        local_clock.return_value = dt_util.as_local(now)
        utc_clock.return_value = now
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == "on"
        assert hass.states.get(ENTITY_ID).attributes["message"] == "Fajr"
        assert (
            hass.states.get("sensor.islamic_prayer_times_current_prayer").state
            == "fajr"
        )
        assert (
            hass.states.get("sensor.islamic_prayer_times_current_prayer_started").state
            == fajr
        )
        assert (
            hass.states.get("sensor.islamic_prayer_times_current_prayer_ends").state
            == sunrise
        )
        assert await get_events(
            hass, now.isoformat(), (now + timedelta(seconds=1)).isoformat()
        ) == [{"summary": "Fajr", "start": fajr, "end": sunrise}]


@pytest.mark.parametrize("time_zone", ["UTC", "Pacific/Auckland", "Etc/GMT+12"])
async def test_next_prayer_through_rollover(
    hass: HomeAssistant, time_zone: str
) -> None:
    """Keep next Fajr known until the following rollover without manual updates."""
    await hass.config.async_set_time_zone(time_zone)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"latitude": -41.2866, "longitude": 174.7756},
        minor_version=2,
    )
    entry.add_to_hass(hass)
    # The calculator requires real date objects, but timers need a frozen wall clock.
    with freeze_time(
        "2025-12-31T12:23:59Z", ignore=["prayer_times_calculator_offline"]
    ) as clock:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert (
            hass.states.get("sensor.islamic_prayer_times_fajr_prayer").state
            == "2025-12-30T15:10:00+00:00"
        )

        # Exercise the real rollover timer, then every boundary through the next Isha.
        for instant in (
            "2025-12-31T12:24:01Z",
            "2025-12-31T15:11:00Z",
            "2025-12-31T16:51:00Z",
            "2026-01-01T00:24:00Z",
            "2026-01-01T04:25:00Z",
            "2026-01-01T07:57:00Z",
            "2026-01-01T09:38:00Z",
            "2026-01-01T10:00:00Z",
        ):
            clock.move_to(instant)
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            assert (
                hass.states.get("sensor.islamic_prayer_times_fajr_prayer").state
                == "2025-12-31T15:11:00+00:00"
            )

        assert hass.states.get(ENTITY_ID).state == "on"
        assert hass.states.get(ENTITY_ID).attributes["message"] == "Isha"
        assert (
            hass.states.get("sensor.islamic_prayer_times_current_prayer").state
            == "isha"
        )
        assert (
            hass.states.get("sensor.islamic_prayer_times_next_prayer").state == "fajr"
        )
        assert (
            hass.states.get("sensor.islamic_prayer_times_next_prayer_starts").state
            == "2026-01-01T15:12:00+00:00"
        )
        assert await get_events(
            hass, "2026-01-01T10:00:00Z", "2026-01-01T16:00:00Z"
        ) == [
            {
                "summary": "Isha",
                "start": "2026-01-01T09:38:00+00:00",
                "end": "2026-01-01T12:24:00+00:00",
            },
            {
                "summary": "Fajr",
                "start": "2026-01-01T15:12:00+00:00",
                "end": "2026-01-01T16:52:00+00:00",
            },
        ]

        clock.move_to("2026-01-01T12:24:01Z")
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (
            hass.states.get("sensor.islamic_prayer_times_fajr_prayer").state
            == "2026-01-01T15:12:00+00:00"
        )
        assert (
            hass.states.get("sensor.islamic_prayer_times_next_prayer_starts").state
            == "2026-01-01T15:12:00+00:00"
        )
