"""The tests for the group calendar platform."""

from collections.abc import Sequence
import datetime as dt
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockPlatform,
    async_fire_time_changed,
    get_fixture_path,
    mock_platform,
)
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant import config as hass_config, config_entries
from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    SERVICE_GET_EVENTS,
    CalendarEntity,
    CalendarEvent,
)
from homeassistant.components.group import DOMAIN, SERVICE_RELOAD
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

GROUP_ENTITY_ID = "calendar.family"
NOW = dt.datetime(2026, 10, 17, 12, 0, tzinfo=dt.UTC)
FAMILY_GROUP = {
    "platform": DOMAIN,
    "entities": ["calendar.work", "calendar.home"],
    "name": "Family",
    "unique_id": "unique_identifier",
}

MEETING = CalendarEvent(
    start=NOW - dt.timedelta(hours=1),
    end=NOW + dt.timedelta(hours=1),
    summary="Meeting",
    location="Office",
)
HOLIDAY = CalendarEvent(
    start=NOW.date(),
    end=NOW.date() + dt.timedelta(days=1),
    summary="Holiday",
)
DINNER = CalendarEvent(
    start=NOW + dt.timedelta(hours=6),
    end=NOW + dt.timedelta(hours=8),
    summary="Dinner",
    description="With friends",
)


class MockCalendarEntity(CalendarEntity):
    """Calendar entity serving a fixed list of events."""

    def __init__(self, name: str, events: list[CalendarEvent]) -> None:
        """Initialize the calendar."""
        self._attr_name = name
        self._events = events
        self.update_count = 0

    async def async_update(self) -> None:
        """Count polling updates."""
        self.update_count += 1

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._events[0] if self._events else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: dt.datetime,
        end_date: dt.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return [
            event
            for event in self._events
            if event.start_datetime_local < end_date
            and event.end_datetime_local > start_date
        ]


@pytest.fixture(autouse=True)
async def set_time_zone(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Use UTC to keep member state attributes readable."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to(NOW)


@pytest.fixture
def calendar_platform(hass: HomeAssistant) -> list[MockCalendarEntity]:
    """Register a calendar platform providing calendar.work and calendar.home."""
    entities = [
        MockCalendarEntity("Work", [MEETING]),
        MockCalendarEntity("Home", [HOLIDAY, DINNER]),
    ]

    async def async_setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        async_add_entities(entities)

    mock_platform(
        hass,
        f"test.{CALENDAR_DOMAIN}",
        MockPlatform(async_setup_platform=async_setup_platform),
    )
    return entities


async def _setup_groups(
    hass: HomeAssistant, groups: Sequence[ConfigType] = (FAMILY_GROUP,)
) -> None:
    """Set up the test calendars and the given calendar groups."""
    await async_setup_component(
        hass,
        CALENDAR_DOMAIN,
        {CALENDAR_DOMAIN: [{"platform": "test"}, *groups]},
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def _update_member(
    hass: HomeAssistant,
    entity: MockCalendarEntity,
    events: list[CalendarEvent],
    available: bool = True,
) -> None:
    """Change the events and availability of a member calendar."""
    entity._events = events
    entity._attr_available = available
    entity.async_write_ha_state()
    await hass.async_block_till_done()


async def test_state(
    hass: HomeAssistant, calendar_platform: list[MockCalendarEntity]
) -> None:
    """Test calendar group state follows the earliest member event."""
    work, home = calendar_platform
    work._attr_available = False
    home._attr_available = False
    await _setup_groups(hass)

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    await _update_member(hass, work, [])

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes == {
        ATTR_ENTITY_ID: ["calendar.work", "calendar.home"],
        "friendly_name": "Family",
    }

    await _update_member(hass, home, [DINNER])

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["message"] == "Dinner"
    assert state.attributes["description"] == "With friends"

    await _update_member(hass, work, [MEETING])

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes == {
        ATTR_ENTITY_ID: ["calendar.work", "calendar.home"],
        "friendly_name": "Family",
        "message": "Meeting",
        "all_day": False,
        "start_time": "2026-10-17 11:00:00",
        "end_time": "2026-10-17 13:00:00",
        "location": "Office",
        "description": "",
    }

    await _update_member(hass, work, [MEETING], available=False)

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["message"] == "Dinner"

    await _update_member(hass, home, [DINNER], available=False)

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("calendar_platform")
async def test_all_day_event(hass: HomeAssistant) -> None:
    """Test an all day member event is preferred when it started earlier."""
    await _setup_groups(hass)

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["message"] == "Holiday"
    assert state.attributes["all_day"] is True
    assert state.attributes["start_time"] == "2026-10-17 00:00:00"
    assert state.attributes["end_time"] == "2026-10-18 00:00:00"


async def test_event_ends(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    calendar_platform: list[MockCalendarEntity],
) -> None:
    """Test the group moves to the next event when the current one ends."""
    calendar_platform[1]._events = [DINNER]
    await _setup_groups(hass)

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["message"] == "Meeting"

    freezer.move_to(NOW + dt.timedelta(hours=1, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["message"] == "Dinner"


async def test_event_in_repeated_dst_hour(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    calendar_platform: list[MockCalendarEntity],
) -> None:
    """Test a member event in the repeated hour at the end of DST keeps its offset."""
    await hass.config.async_set_time_zone("America/New_York")
    # 01:00 EST, after clocks went back from 02:00 EDT
    freezer.move_to(dt.datetime(2026, 11, 1, 6, 0, tzinfo=dt.UTC))
    work, home = calendar_platform
    work._events = [
        CalendarEvent(
            start=dt.datetime(2026, 11, 1, 6, 30, tzinfo=dt.UTC),
            end=dt.datetime(2026, 11, 1, 7, 0, tzinfo=dt.UTC),
            summary="Night shift",
        )
    ]
    home._events = []
    await _setup_groups(hass)

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["message"] == "Night shift"
    assert state.attributes["start_time"] == "2026-11-01 01:30:00"
    # The state attribute is ambiguous in local time, the group event is not
    group = hass.data[CALENDAR_DOMAIN].get_entity(GROUP_ENTITY_ID)
    assert group.event.start == dt.datetime(2026, 11, 1, 6, 30, tzinfo=dt.UTC)


async def test_events_ordered_across_repeated_dst_hour(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    calendar_platform: list[MockCalendarEntity],
) -> None:
    """Test events in both passes of the repeated DST hour are ordered by instant."""
    await hass.config.async_set_time_zone("America/New_York")
    # 01:30 EDT, the first pass through the repeated hour
    freezer.move_to(dt.datetime(2026, 11, 1, 5, 30, tzinfo=dt.UTC))
    work, home = calendar_platform
    # 01:00 EDT to 01:15 EST
    work._events = [
        CalendarEvent(
            start=dt.datetime(2026, 11, 1, 5, 0, tzinfo=dt.UTC),
            end=dt.datetime(2026, 11, 1, 6, 15, tzinfo=dt.UTC),
            summary="Shift",
        )
    ]
    home._events = [
        # 01:10 EST to 01:40 EST
        CalendarEvent(
            start=dt.datetime(2026, 11, 1, 6, 10, tzinfo=dt.UTC),
            end=dt.datetime(2026, 11, 1, 6, 40, tzinfo=dt.UTC),
            summary="Late call",
        ),
        # 01:45 EDT to 01:50 EDT
        CalendarEvent(
            start=dt.datetime(2026, 11, 1, 5, 45, tzinfo=dt.UTC),
            end=dt.datetime(2026, 11, 1, 5, 50, tzinfo=dt.UTC),
            summary="Early call",
        ),
    ]
    await _setup_groups(hass)

    group = hass.data[CALENDAR_DOMAIN].get_entity(GROUP_ENTITY_ID)
    assert group.event.summary == "Shift"

    events = await group.async_get_events(
        hass,
        dt_util.start_of_local_day(),
        dt_util.start_of_local_day() + dt.timedelta(days=1),
    )
    assert [event.summary for event in events] == ["Shift", "Early call", "Late call"]


async def test_state_membership_cycle(
    hass: HomeAssistant, calendar_platform: list[MockCalendarEntity]
) -> None:
    """Test a group including itself doesn't keep its own previous event."""
    work, home = calendar_platform
    home._events = []
    await _setup_groups(
        hass,
        [
            {
                "platform": DOMAIN,
                "name": "Family",
                "entities": ["calendar.work", GROUP_ENTITY_ID],
            }
        ],
    )

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["message"] == "Meeting"

    await _update_member(hass, work, [])

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert "message" not in state.attributes

    await _update_member(hass, work, [], available=False)

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_get_events(
    hass: HomeAssistant, calendar_platform: list[MockCalendarEntity]
) -> None:
    """Test the group returns the events of all members."""
    await _setup_groups(hass)

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["message"] == "Holiday"

    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: GROUP_ENTITY_ID,
            "start_date_time": dt_util.start_of_local_day(),
            "duration": {"days": 1},
        },
        blocking=True,
        return_response=True,
    )
    assert response == {
        GROUP_ENTITY_ID: {
            "events": [
                {
                    "start": "2026-10-17",
                    "end": "2026-10-18",
                    "summary": "Holiday",
                },
                {
                    "start": "2026-10-17T11:00:00+00:00",
                    "end": "2026-10-17T13:00:00+00:00",
                    "summary": "Meeting",
                    "location": "Office",
                },
                {
                    "start": "2026-10-17T18:00:00+00:00",
                    "end": "2026-10-17T20:00:00+00:00",
                    "summary": "Dinner",
                    "description": "With friends",
                },
            ]
        }
    }

    # Members are not refreshed by the group fetching their events
    assert [entity.update_count for entity in calendar_platform] == [0, 0]


@pytest.mark.parametrize(
    ("groups", "expected_summaries"),
    [
        pytest.param(
            [{"name": "Family", "entities": ["calendar.work", "calendar.family"]}],
            ["Meeting"],
            id="self_reference",
        ),
        pytest.param(
            [
                {"name": "Family", "entities": ["calendar.work", "calendar.friends"]},
                {"name": "Friends", "entities": ["calendar.home", "calendar.family"]},
            ],
            ["Holiday", "Meeting", "Dinner"],
            id="two_group_cycle",
        ),
        pytest.param(
            [
                {"name": "Family", "entities": ["calendar.work", "calendar.friends"]},
                {"name": "Friends", "entities": ["calendar.work"]},
            ],
            ["Meeting"],
            id="shared_member",
        ),
    ],
)
@pytest.mark.usefixtures("calendar_platform")
async def test_get_events_nested_groups(
    hass: HomeAssistant,
    groups: list[ConfigType],
    expected_summaries: list[str],
) -> None:
    """Test nested groups fetch each calendar once, even with membership cycles."""
    await _setup_groups(hass, [{"platform": DOMAIN, **group} for group in groups])

    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: GROUP_ENTITY_ID,
            "start_date_time": dt_util.start_of_local_day(),
            "duration": {"days": 1},
        },
        blocking=True,
        return_response=True,
    )
    assert [
        event["summary"] for event in response[GROUP_ENTITY_ID]["events"]
    ] == expected_summaries


async def test_nested_group_report_refreshes_member_events(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    calendar_platform: list[MockCalendarEntity],
) -> None:
    """Test a parent group picks up later event changes inside a nested group."""
    home = calendar_platform[1]
    home._events = [DINNER]
    await _setup_groups(
        hass,
        [
            {"platform": DOMAIN, "name": "Family", "entities": ["calendar.friends"]},
            {
                "platform": DOMAIN,
                "name": "Friends",
                "entities": ["calendar.work", "calendar.home"],
            },
        ],
    )

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.attributes["message"] == "Meeting"

    # The nested group's earliest event is still the meeting, so it only
    # reports an unchanged state
    await _update_member(
        hass,
        home,
        [
            CalendarEvent(
                start=NOW + dt.timedelta(hours=9),
                end=NOW + dt.timedelta(hours=10),
                summary="Movie",
            )
        ],
    )

    freezer.move_to(NOW + dt.timedelta(hours=1, minutes=1))
    group = hass.data[CALENDAR_DOMAIN].get_entity(GROUP_ENTITY_ID)
    assert group.event.summary == "Movie"


async def test_reload(hass: HomeAssistant) -> None:
    """Test reloading YAML calendar groups."""
    await async_setup_component(
        hass,
        CALENDAR_DOMAIN,
        {
            CALENDAR_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["calendar.work", "calendar.home"],
                "name": "Family",
            }
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get(GROUP_ENTITY_ID) is not None

    yaml_path = get_fixture_path("calendar_configuration.yaml", DOMAIN)
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, {}, blocking=True)
        await hass.async_block_till_done()

    assert hass.states.get(GROUP_ENTITY_ID) is None
    assert hass.states.get("calendar.friends") is not None


async def test_subscribe_updates_on_member_report(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    calendar_platform: list[MockCalendarEntity],
) -> None:
    """Test subscribers are updated when a member refreshes without a state change."""
    await _setup_groups(hass)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "calendar/event/subscribe",
            "entity_id": GROUP_ENTITY_ID,
            "start": dt_util.start_of_local_day().isoformat(),
            "end": (dt_util.start_of_local_day() + dt.timedelta(days=1)).isoformat(),
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    subscription_id = msg["id"]

    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert len(msg["event"]["events"]) == 3

    # A later event doesn't change the member's current event, so its state
    # write is reported instead of changed
    home = calendar_platform[1]
    home._events.append(
        CalendarEvent(
            start=NOW + dt.timedelta(hours=9),
            end=NOW + dt.timedelta(hours=10),
            summary="Movie",
        )
    )
    home.async_write_ha_state()
    await hass.async_block_till_done()

    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert [event["summary"] for event in msg["event"]["events"]] == [
        "Holiday",
        "Meeting",
        "Dinner",
        "Movie",
    ]


@pytest.mark.usefixtures("calendar_platform")
async def test_config_entry(hass: HomeAssistant) -> None:
    """Test a calendar group set up from a config entry."""
    await _setup_groups(hass, [])
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            "entities": ["calendar.work", "calendar.home"],
            "group_type": "calendar",
            "hide_members": False,
            "name": "Family",
        },
        title="Family",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(GROUP_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_ENTITY_ID] == ["calendar.work", "calendar.home"]
    assert state.attributes["message"] == "Holiday"


@pytest.mark.usefixtures("calendar_platform")
async def test_config_flow_preview(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the calendar group preview."""
    await _setup_groups(hass, [])
    client = await hass_ws_client(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "calendar"}
    )
    assert result["preview"] == "group"

    await client.send_json_auto_id(
        {
            "type": "group/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {
                "name": "Family",
                "entities": ["calendar.work", "calendar.home"],
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    msg = await client.receive_json()
    assert msg["event"] == {
        "attributes": {
            ATTR_ENTITY_ID: ["calendar.work", "calendar.home"],
            "friendly_name": "Family",
            "message": "Holiday",
            "all_day": True,
            "start_time": "2026-10-17 00:00:00",
            "end_time": "2026-10-18 00:00:00",
            "location": "",
            "description": "",
        },
        "state": STATE_ON,
    }


async def test_config_flow_preview_calendar_not_loaded(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the preview is unavailable before the calendar integration is loaded."""
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "calendar"}
    )

    await client.send_json_auto_id(
        {
            "type": "group/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {"name": "Family", "entities": ["calendar.work"]},
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    msg = await client.receive_json()
    assert msg["event"] == {
        "attributes": {"friendly_name": "Family"},
        "state": STATE_UNAVAILABLE,
    }
