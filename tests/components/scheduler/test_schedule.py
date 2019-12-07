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
    end_datetime = start_datetime + timedelta(days=1)

    # 1. A schedule with a start datetime only:
    schedule = Schedule(hass, "scene.test_scene_1", start_datetime)
    assert not schedule.active
    assert not schedule.expired
    assert (
        str(schedule) == f'<Schedule start="{start_datetime}" end="None" rrule="None">'
    )
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
    assert not schedule.active
    assert not schedule.expired
    assert (
        str(schedule)
        == f'<Schedule start="{start_datetime}" end="{end_datetime}" rrule="None">'
    )
    assert schedule.as_dict() == {
        CONF_ENTITY_ID: "scene.test_scene_2",
        CONF_START_DATETIME: start_datetime.isoformat(),
        CONF_END_DATETIME: end_datetime.isoformat(),
        CONF_RECURRENCE: None,
    }

    # 2. A schedule with a start datetime, an end datetime, and a recurrence:
    start_datetime_rfc5545 = (
        start_datetime.isoformat().split(".")[0].replace("-", "").replace(":", "")
    )
    schedule = Schedule(
        hass,
        "scene.test_scene_3",
        start_datetime,
        end_datetime=end_datetime,
        recurrence=rrule(DAILY, dtstart=start_datetime),
    )
    assert schedule.active
    assert not schedule.expired
    assert str(schedule) == (
        f'<Schedule start="{start_datetime}" end="{end_datetime}" '
        f'rrule="DTSTART:{start_datetime_rfc5545}\nRRULE:FREQ=DAILY">'
    )
    assert schedule.as_dict() == {
        CONF_ENTITY_ID: "scene.test_scene_3",
        CONF_START_DATETIME: start_datetime.isoformat(),
        CONF_END_DATETIME: end_datetime.isoformat(),
        CONF_RECURRENCE: f"DTSTART:{start_datetime_rfc5545}\nRRULE:FREQ=DAILY",
    }
