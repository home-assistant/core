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
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed


async def test_manually_create_expired_schedule(hass):
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
    assert not schedule.is_on
    assert schedule.state == "expired"
    assert schedule.as_dict() == {
        CONF_ENTITY_ID: "scene.test_scene_1",
        CONF_START_DATETIME: start_datetime.isoformat(),
        CONF_END_DATETIME: None,
        CONF_RECURRENCE: None,
    }
    assert not schedule.active_instance

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
    assert not schedule.is_on
    assert schedule.state == "off"
    assert schedule.as_dict() == {
        CONF_ENTITY_ID: "scene.test_scene_2",
        CONF_START_DATETIME: start_datetime.isoformat(),
        CONF_END_DATETIME: None,
        CONF_RECURRENCE: f"DTSTART:{start_datetime_rfc5545}\nRRULE:FREQ=DAILY",
    }
    assert not schedule.active_instance


async def test_manually_create_schedule(hass):
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
    assert not schedule.active_instance

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
    assert not schedule.active_instance

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
    assert not schedule.is_on
    assert schedule.state == "off"
    assert schedule.as_dict() == {
        CONF_ENTITY_ID: "scene.test_scene_3",
        CONF_START_DATETIME: start_datetime.isoformat(),
        CONF_END_DATETIME: None,
        CONF_RECURRENCE: f"DTSTART:{start_datetime_rfc5545}\nRRULE:FREQ=DAILY",
    }
    assert not schedule.active_instance

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
    assert not schedule.is_on
    assert schedule.state == "off"
    assert schedule.as_dict() == {
        CONF_ENTITY_ID: "scene.test_scene_4",
        CONF_START_DATETIME: start_datetime.isoformat(),
        CONF_END_DATETIME: end_datetime.isoformat(),
        CONF_RECURRENCE: f"DTSTART:{start_datetime_rfc5545}\nRRULE:FREQ=DAILY",
    }
    assert not schedule.active_instance


async def test_create_schedule(hass, scheduler):
    """Test creating a schedule with a start datetime."""
    assert await async_setup_component(hass, "light", {"light": {"platform": "demo"}})
    assert hass.states.get("light.bed_light").state == "off"
    assert await async_setup_component(
        hass,
        "scene",
        {"scene": {"name": "test_scene_1", "entities": {"light.bed_light": "on"}}},
    )

    start_datetime = dt_util.utcnow() + timedelta(hours=1)
    schedule = Schedule(hass, "scene.test_scene_1", start_datetime)
    scheduler.async_create(schedule)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, start_datetime)
    await hass.async_block_till_done()
    assert hass.states.get("light.bed_light").state == "on"
    assert not schedule.active_instance


async def test_schedule_instance_with_start_and_recurrence(hass, scheduler):
    """Test creating a schedule with a start datetime and a recurrence."""
    assert await async_setup_component(hass, "light", {"light": {"platform": "demo"}})
    assert hass.states.get("light.bed_light").state == "off"
    assert await async_setup_component(
        hass,
        "scene",
        {"scene": {"name": "test_scene_1", "entities": {"light.bed_light": "on"}}},
    )

    original_state = hass.states.get("light.bed_light")

    start_datetime = dt_util.utcnow() + timedelta(hours=1)
    schedule = Schedule(
        hass,
        "scene.test_scene_1",
        start_datetime,
        recurrence=rrule(DAILY, dtstart=start_datetime),
    )
    scheduler.async_create(schedule)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, start_datetime)
    await hass.async_block_till_done()
    assert hass.states.get("light.bed_light").state == "on"
    assert not schedule.active_instance

    # Reset the light before the next schedule instance:
    await hass.services.async_call(
        "scene",
        "apply",
        service_data={"entities": {"light.bed_light": original_state.as_dict()}},
        blocking=True,
    )
    assert hass.states.get("light.bed_light").state == "off"
    next_start_datetime = schedule.recurrence.after(start_datetime)

    async_fire_time_changed(hass, next_start_datetime)
    await hass.async_block_till_done()
    assert hass.states.get("light.bed_light").state == "on"
    assert not schedule.active_instance


async def test_schedule_instance_with_end(hass, scheduler):
    """Test creating a schedule with a end datetime."""
    assert await async_setup_component(hass, "light", {"light": {"platform": "demo"}})
    assert hass.states.get("light.bed_light").state == "off"
    assert await async_setup_component(
        hass,
        "scene",
        {"scene": {"name": "test_scene_1", "entities": {"light.bed_light": "on"}}},
    )

    start_datetime = dt_util.utcnow() + timedelta(hours=1)
    end_datetime = start_datetime + timedelta(hours=1)
    schedule = Schedule(
        hass, "scene.test_scene_1", start_datetime, end_datetime=end_datetime
    )
    scheduler.async_create(schedule)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, start_datetime)
    await hass.async_block_till_done()
    assert hass.states.get("light.bed_light").state == "on"
    assert schedule.active_instance

    async_fire_time_changed(hass, end_datetime)
    await hass.async_block_till_done()
    assert hass.states.get("light.bed_light").state == "off"
    assert not schedule.active_instance


async def test_schedule_instance_with_end_and_recurrence(hass, scheduler):
    """Test creating a schedule with a start datetime, end datetime, and a recurrence."""
    assert await async_setup_component(hass, "light", {"light": {"platform": "demo"}})
    assert hass.states.get("light.bed_light").state == "off"
    assert await async_setup_component(
        hass,
        "scene",
        {"scene": {"name": "test_scene_1", "entities": {"light.bed_light": "on"}}},
    )

    original_state = hass.states.get("light.bed_light")

    start_datetime = dt_util.utcnow() + timedelta(hours=1)
    end_datetime = start_datetime + timedelta(hours=1)
    schedule = Schedule(
        hass,
        "scene.test_scene_1",
        start_datetime,
        end_datetime=end_datetime,
        recurrence=rrule(DAILY, dtstart=start_datetime),
    )
    scheduler.async_create(schedule)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, start_datetime)
    await hass.async_block_till_done()
    assert hass.states.get("light.bed_light").state == "on"
    assert schedule.active_instance

    async_fire_time_changed(hass, end_datetime)
    await hass.async_block_till_done()
    assert hass.states.get("light.bed_light").state == "off"
    assert schedule.active_instance

    # Reset the light before the next schedule instance:
    await hass.services.async_call(
        "scene",
        "apply",
        service_data={"entities": {"light.bed_light": original_state.as_dict()}},
        blocking=True,
    )
    assert hass.states.get("light.bed_light").state == "off"
    next_start_datetime = schedule.recurrence.after(start_datetime)

    async_fire_time_changed(hass, next_start_datetime)
    await hass.async_block_till_done()
    assert hass.states.get("light.bed_light").state == "on"
    assert schedule.active_instance

    async_fire_time_changed(hass, next_start_datetime + timedelta(hours=1))
    await hass.async_block_till_done()
    assert hass.states.get("light.bed_light").state == "off"
    assert schedule.active_instance
