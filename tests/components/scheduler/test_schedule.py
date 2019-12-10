"""Define tests for the Schedule and ScheduleInstance objects."""
from datetime import timedelta

from dateutil.rrule import DAILY, rrule

from homeassistant.components.scheduler.schedule import (
    CONF_END_DATETIME,
    CONF_RECURRENCE,
    CONF_START_DATETIME,
    Schedule,
)
from homeassistant.const import CONF_ENTITY_ID
import homeassistant.util.dt as dt_util


async def test_create_schedule(hass):
    """Test creating a schedule (in various forms)."""
    start_datetime = dt_util.utcnow() + timedelta(hours=1)
    start_datetime_rfc5545 = (
        start_datetime.isoformat().split(".")[0].replace("-", "").replace(":", "")
    )
    end_datetime = start_datetime + timedelta(days=1)

    # 1. A schedule with a start datetime only:
    schedule = Schedule(hass, "scene.test_scene_1", start_datetime)
    assert (
        str(schedule) == f'<Schedule start="{start_datetime}" end="None" rrule="None">'
    )
    assert not schedule.active
    assert not schedule.expired
    assert schedule.state == "off"
    assert schedule.as_dict() == {
        CONF_ENTITY_ID: "scene.test_scene_1",
        CONF_START_DATETIME: start_datetime.isoformat(),
        CONF_END_DATETIME: None,
        CONF_RECURRENCE: None,
    }

    # 2. A schedule with a start datetime and an end datetime:
    schedule = Schedule(
        hass, "scene.test_scene_2", start_datetime, end_datetime=end_datetime,
    )
    assert (
        str(schedule)
        == f'<Schedule start="{start_datetime}" end="{end_datetime}" rrule="None">'
    )
    assert not schedule.active
    assert not schedule.expired
    assert schedule.state == "off"
    assert schedule.as_dict() == {
        CONF_ENTITY_ID: "scene.test_scene_2",
        CONF_START_DATETIME: start_datetime.isoformat(),
        CONF_END_DATETIME: end_datetime.isoformat(),
        CONF_RECURRENCE: None,
    }

    # 3. A schedule with a start datetime and a recurrence:
    schedule = Schedule(
        hass,
        "scene.test_scene_3",
        start_datetime,
        end_datetime=None,
        recurrence=rrule(DAILY, dtstart=start_datetime),
    )
    assert str(schedule) == (
        f'<Schedule start="{start_datetime}" end="None" '
        f'rrule="DTSTART:{start_datetime_rfc5545}\nRRULE:FREQ=DAILY">'
    )
    assert not schedule.active
    assert not schedule.expired
    assert schedule.state == "off"
    assert schedule.as_dict() == {
        CONF_ENTITY_ID: "scene.test_scene_3",
        CONF_START_DATETIME: start_datetime.isoformat(),
        CONF_END_DATETIME: None,
        CONF_RECURRENCE: f"DTSTART:{start_datetime_rfc5545}\nRRULE:FREQ=DAILY",
    }

    # 4. A schedule with a start datetime, an end datetime, and a recurrence:
    schedule = Schedule(
        hass,
        "scene.test_scene_4",
        start_datetime,
        end_datetime=end_datetime,
        recurrence=rrule(DAILY, dtstart=start_datetime),
    )
    assert str(schedule) == (
        f'<Schedule start="{start_datetime}" end="{end_datetime}" '
        f'rrule="DTSTART:{start_datetime_rfc5545}\nRRULE:FREQ=DAILY">'
    )
    assert not schedule.active
    assert not schedule.expired
    assert schedule.state == "off"
    assert schedule.as_dict() == {
        CONF_ENTITY_ID: "scene.test_scene_4",
        CONF_START_DATETIME: start_datetime.isoformat(),
        CONF_END_DATETIME: end_datetime.isoformat(),
        CONF_RECURRENCE: f"DTSTART:{start_datetime_rfc5545}\nRRULE:FREQ=DAILY",
    }


async def test_expired_schedule(hass):
    """Test that an expired schedule appears as it should."""
    start_datetime = dt_util.utcnow() - timedelta(hours=1)
    start_datetime_rfc5545 = (
        start_datetime.isoformat().split(".")[0].replace("-", "").replace(":", "")
    )

    # 1. A schedule with a start datetime in the past:
    schedule = Schedule(hass, "scene.test_scene_1", start_datetime)
    assert (
        str(schedule) == f'<Schedule start="{start_datetime}" end="None" rrule="None">'
    )
    assert not schedule.active
    assert schedule.expired
    assert schedule.state == "expired"
    assert schedule.as_dict() == {
        CONF_ENTITY_ID: "scene.test_scene_1",
        CONF_START_DATETIME: start_datetime.isoformat(),
        CONF_END_DATETIME: None,
        CONF_RECURRENCE: None,
    }

    # 2. A schedule with a start datetime in the past, but a future-facing recurrence:
    schedule = Schedule(
        hass,
        "scene.test_scene_2",
        start_datetime,
        end_datetime=None,
        recurrence=rrule(DAILY, dtstart=start_datetime),
    )
    assert str(schedule) == (
        f'<Schedule start="{start_datetime}" end="None" '
        f'rrule="DTSTART:{start_datetime_rfc5545}\nRRULE:FREQ=DAILY">'
    )
    assert not schedule.active
    assert not schedule.expired
    assert schedule.state == "off"
    assert schedule.as_dict() == {
        CONF_ENTITY_ID: "scene.test_scene_2",
        CONF_START_DATETIME: start_datetime.isoformat(),
        CONF_END_DATETIME: None,
        CONF_RECURRENCE: f"DTSTART:{start_datetime_rfc5545}\nRRULE:FREQ=DAILY",
    }
