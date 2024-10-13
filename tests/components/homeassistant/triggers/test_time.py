"""The tests for the time automation."""

from datetime import timedelta
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant.components import automation
from homeassistant.components.homeassistant.triggers import time
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import assert_setup_component, async_fire_time_changed, mock_component


@pytest.fixture(autouse=True)
def setup_comp(hass: HomeAssistant) -> None:
    """Initialize components."""
    mock_component(hass, "group")


async def test_if_fires_using_at(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
) -> None:
    """Test for firing at."""
    now = dt_util.now()

    trigger_dt = now.replace(hour=5, minute=0, second=0, microsecond=0) + timedelta(2)
    time_that_will_not_match_right_away = trigger_dt - timedelta(minutes=1)

    freezer.move_to(time_that_will_not_match_right_away)
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "time", "at": "5:00:00"},
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": "{{ trigger.platform }} - {{ trigger.now.hour }}",
                        "id": "{{ trigger.id}}",
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()

    async_fire_time_changed(hass, trigger_dt + timedelta(seconds=1))
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "time - 5"
    assert service_calls[0].data["id"] == 0


@pytest.mark.parametrize(
    ("has_date", "has_time"), [(True, True), (True, False), (False, True)]
)
async def test_if_fires_using_at_input_datetime(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
    has_date,
    has_time,
) -> None:
    """Test for firing at input_datetime."""
    await async_setup_component(
        hass,
        "input_datetime",
        {"input_datetime": {"trigger": {"has_date": has_date, "has_time": has_time}}},
    )
    now = dt_util.now()

    trigger_dt = now.replace(
        hour=5 if has_time else 0, minute=0, second=0, microsecond=0
    ) + timedelta(2)

    await hass.services.async_call(
        "input_datetime",
        "set_datetime",
        {
            ATTR_ENTITY_ID: "input_datetime.trigger",
            "datetime": str(trigger_dt.replace(tzinfo=None)),
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    time_that_will_not_match_right_away = trigger_dt - timedelta(minutes=1)

    some_data = "{{ trigger.platform }}-{{ trigger.now.day }}-{{ trigger.now.hour }}-{{trigger.entity_id}}"

    freezer.move_to(dt_util.as_utc(time_that_will_not_match_right_away))
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "time", "at": "input_datetime.trigger"},
                "action": {
                    "service": "test.automation",
                    "data_template": {"some": some_data},
                },
            }
        },
    )
    await hass.async_block_till_done()

    async_fire_time_changed(hass, trigger_dt + timedelta(seconds=1))
    await hass.async_block_till_done()

    assert len(service_calls) == 2
    assert (
        service_calls[1].data["some"]
        == f"time-{trigger_dt.day}-{trigger_dt.hour}-input_datetime.trigger"
    )

    if has_date:
        trigger_dt += timedelta(days=1)
    if has_time:
        trigger_dt += timedelta(hours=1)

    await hass.services.async_call(
        "input_datetime",
        "set_datetime",
        {
            ATTR_ENTITY_ID: "input_datetime.trigger",
            "datetime": str(trigger_dt.replace(tzinfo=None)),
        },
        blocking=True,
    )
    assert len(service_calls) == 3
    await hass.async_block_till_done()

    async_fire_time_changed(hass, trigger_dt + timedelta(seconds=1))
    await hass.async_block_till_done()

    assert len(service_calls) == 4
    assert (
        service_calls[3].data["some"]
        == f"time-{trigger_dt.day}-{trigger_dt.hour}-input_datetime.trigger"
    )


@pytest.mark.parametrize(
    ("conf_at", "trigger_deltas"),
    [
        (["5:00:00", "6:00:00"], [timedelta(0), timedelta(hours=1)]),
        (
            [
                "5:00:05",
                {"entity_id": "sensor.next_alarm", "offset": "00:00:10"},
                "sensor.next_alarm",
            ],
            [timedelta(seconds=5), timedelta(seconds=10), timedelta(0)],
        ),
    ],
)
async def test_if_fires_using_multiple_at(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
    conf_at: list[str | dict[str, int | str]],
    trigger_deltas: list[timedelta],
) -> None:
    """Test for firing at multiple trigger times."""

    now = dt_util.now()

    start_dt = now.replace(hour=5, minute=0, second=0, microsecond=0) + timedelta(2)

    hass.states.async_set(
        "sensor.next_alarm",
        start_dt.isoformat(),
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP},
    )

    time_that_will_not_match_right_away = start_dt - timedelta(minutes=1)

    freezer.move_to(dt_util.as_utc(time_that_will_not_match_right_away))
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "time", "at": conf_at},
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": "{{ trigger.platform }} - {{ trigger.now.hour }}"
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()

    for count, delta in enumerate(sorted(trigger_deltas)):
        async_fire_time_changed(hass, start_dt + delta + timedelta(seconds=1))
        await hass.async_block_till_done()

        assert len(service_calls) == count + 1
        assert (
            service_calls[count].data["some"] == f"time - {5 + (delta.seconds // 3600)}"
        )


async def test_if_not_fires_using_wrong_at(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
) -> None:
    """YAML translates time values to total seconds.

    This should break the before rule.
    """
    now = dt_util.utcnow()

    time_that_will_not_match_right_away = now.replace(
        year=now.year + 1, day=1, hour=1, minute=0, second=0
    )

    freezer.move_to(time_that_will_not_match_right_away)
    with assert_setup_component(1, automation.DOMAIN):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "time",
                        "at": 3605,
                        # Total seconds. Hour = 3600 second
                    },
                    "action": {"service": "test.automation"},
                }
            },
        )
    await hass.async_block_till_done()
    assert hass.states.get("automation.automation_0").state == STATE_UNAVAILABLE

    async_fire_time_changed(
        hass, now.replace(year=now.year + 1, day=1, hour=1, minute=0, second=5)
    )

    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_if_action_before(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test for if action before."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "time", "before": "10:00"},
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    before_10 = dt_util.now().replace(hour=8)
    after_10 = dt_util.now().replace(hour=14)

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=before_10):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(service_calls) == 1

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=after_10):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_if_action_after(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test for if action after."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "time", "after": "10:00"},
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    before_10 = dt_util.now().replace(hour=8)
    after_10 = dt_util.now().replace(hour=14)

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=before_10):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(service_calls) == 0

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=after_10):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_if_action_one_weekday(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test for if action with one weekday."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "time", "weekday": "mon"},
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    days_past_monday = dt_util.now().weekday()
    monday = dt_util.now() - timedelta(days=days_past_monday)
    tuesday = monday + timedelta(days=1)

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=monday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(service_calls) == 1

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=tuesday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_if_action_list_weekday(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test for action with a list of weekdays."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "time", "weekday": ["mon", "tue"]},
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    days_past_monday = dt_util.now().weekday()
    monday = dt_util.now() - timedelta(days=days_past_monday)
    tuesday = monday + timedelta(days=1)
    wednesday = tuesday + timedelta(days=1)

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=monday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(service_calls) == 1

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=tuesday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(service_calls) == 2

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=wednesday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(service_calls) == 2


async def test_untrack_time_change(hass: HomeAssistant) -> None:
    """Test for removing tracked time changes."""
    mock_track_time_change = Mock()
    with patch(
        "homeassistant.components.homeassistant.triggers.time.async_track_time_change",
        return_value=mock_track_time_change,
    ):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "alias": "test",
                    "trigger": {
                        "platform": "time",
                        "at": ["5:00:00", "6:00:00", "7:00:00"],
                    },
                    "action": {"service": "test.automation", "data": {"test": "test"}},
                }
            },
        )
        await hass.async_block_till_done()

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "automation.test"},
        blocking=True,
    )

    assert len(mock_track_time_change.mock_calls) == 3


async def test_if_fires_using_at_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
) -> None:
    """Test for firing at sensor time."""
    now = dt_util.now()

    trigger_dt = now.replace(hour=5, minute=0, second=0, microsecond=0) + timedelta(2)

    hass.states.async_set(
        "sensor.next_alarm",
        trigger_dt.isoformat(),
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP},
    )

    time_that_will_not_match_right_away = trigger_dt - timedelta(minutes=1)

    some_data = "{{ trigger.platform }}-{{ trigger.now.day }}-{{ trigger.now.hour }}-{{trigger.entity_id}}"

    freezer.move_to(dt_util.as_utc(time_that_will_not_match_right_away))
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "time", "at": "sensor.next_alarm"},
                "action": {
                    "service": "test.automation",
                    "data_template": {"some": some_data},
                },
            }
        },
    )
    await hass.async_block_till_done()

    async_fire_time_changed(hass, trigger_dt + timedelta(seconds=1))
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert (
        service_calls[0].data["some"]
        == f"time-{trigger_dt.day}-{trigger_dt.hour}-sensor.next_alarm"
    )

    trigger_dt += timedelta(days=1, hours=1)

    hass.states.async_set(
        "sensor.next_alarm",
        trigger_dt.isoformat(),
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP},
    )
    await hass.async_block_till_done()

    async_fire_time_changed(hass, trigger_dt + timedelta(seconds=1))
    await hass.async_block_till_done()

    assert len(service_calls) == 2
    assert (
        service_calls[1].data["some"]
        == f"time-{trigger_dt.day}-{trigger_dt.hour}-sensor.next_alarm"
    )

    for broken in ("unknown", "unavailable", "invalid-ts"):
        hass.states.async_set(
            "sensor.next_alarm",
            trigger_dt.isoformat(),
            {ATTR_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP},
        )
        await hass.async_block_till_done()
        hass.states.async_set(
            "sensor.next_alarm",
            broken,
            {ATTR_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP},
        )
        await hass.async_block_till_done()

        async_fire_time_changed(hass, trigger_dt + timedelta(seconds=1))
        await hass.async_block_till_done()

        # We should not have listened to anything
        assert len(service_calls) == 2

    # Now without device class
    hass.states.async_set(
        "sensor.next_alarm",
        trigger_dt.isoformat(),
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP},
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        "sensor.next_alarm",
        trigger_dt.isoformat(),
    )
    await hass.async_block_till_done()

    async_fire_time_changed(hass, trigger_dt + timedelta(seconds=1))
    await hass.async_block_till_done()

    # We should not have listened to anything
    assert len(service_calls) == 2


@pytest.mark.parametrize(
    ("offset", "delta"),
    [
        ("00:00:10", timedelta(seconds=10)),
        ("-00:00:10", timedelta(seconds=-10)),
        ({"minutes": 5}, timedelta(minutes=5)),
    ],
)
async def test_if_fires_using_at_sensor_with_offset(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    freezer: FrozenDateTimeFactory,
    offset: str | dict[str, int],
    delta: timedelta,
) -> None:
    """Test for firing at sensor time."""
    now = dt_util.now()

    start_dt = now.replace(hour=5, minute=0, second=0, microsecond=0) + timedelta(2)
    trigger_dt = start_dt + delta

    hass.states.async_set(
        "sensor.next_alarm",
        start_dt.isoformat(),
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP},
    )

    time_that_will_not_match_right_away = trigger_dt - timedelta(minutes=1)

    some_data = "{{ trigger.platform }}-{{ trigger.now.day }}-{{ trigger.now.hour }}-{{ trigger.now.minute }}-{{ trigger.now.second }}-{{trigger.entity_id}}"

    freezer.move_to(dt_util.as_utc(time_that_will_not_match_right_away))
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "time",
                    "at": {
                        "entity_id": "sensor.next_alarm",
                        "offset": offset,
                    },
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {"some": some_data},
                },
            }
        },
    )
    await hass.async_block_till_done()

    async_fire_time_changed(hass, trigger_dt + timedelta(seconds=1))
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert (
        service_calls[0].data["some"]
        == f"time-{trigger_dt.day}-{trigger_dt.hour}-{trigger_dt.minute}-{trigger_dt.second}-sensor.next_alarm"
    )

    start_dt += timedelta(days=1, hours=1)
    trigger_dt += timedelta(days=1, hours=1)

    hass.states.async_set(
        "sensor.next_alarm",
        start_dt.isoformat(),
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP},
    )
    await hass.async_block_till_done()

    async_fire_time_changed(hass, trigger_dt + timedelta(seconds=1))
    await hass.async_block_till_done()

    assert len(service_calls) == 2
    assert (
        service_calls[1].data["some"]
        == f"time-{trigger_dt.day}-{trigger_dt.hour}-{trigger_dt.minute}-{trigger_dt.second}-sensor.next_alarm"
    )


@pytest.mark.parametrize(
    "conf",
    [
        {"platform": "time", "at": "input_datetime.bla"},
        {"platform": "time", "at": "sensor.bla"},
        {"platform": "time", "at": "12:34"},
        {"platform": "time", "at": {"entity_id": "sensor.bla", "offset": "-00:01"}},
        {
            "platform": "time",
            "at": [{"entity_id": "sensor.bla", "offset": "-01:00:00"}],
        },
    ],
)
def test_schema_valid(conf) -> None:
    """Make sure we don't accept number for 'at' value."""
    time.TRIGGER_SCHEMA(conf)


@pytest.mark.parametrize(
    "conf",
    [
        {"platform": "time", "at": "binary_sensor.bla"},
        {"platform": "time", "at": 745},
        {"platform": "time", "at": "25:00"},
        {
            "platform": "time",
            "at": {"entity_id": "input_datetime.bla", "offset": "0:10"},
        },
        {"platform": "time", "at": {"entity_id": "13:00:00", "offset": "0:10"}},
    ],
)
def test_schema_invalid(conf) -> None:
    """Make sure we don't accept number for 'at' value."""
    with pytest.raises(vol.Invalid):
        time.TRIGGER_SCHEMA(conf)


async def test_datetime_in_past_on_load(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test time trigger works if input_datetime is in past."""
    await async_setup_component(
        hass,
        "input_datetime",
        {"input_datetime": {"my_trigger": {"has_date": True, "has_time": True}}},
    )

    now = dt_util.now()
    past = now - timedelta(days=2)
    future = now + timedelta(days=1)

    await hass.services.async_call(
        "input_datetime",
        "set_datetime",
        {
            ATTR_ENTITY_ID: "input_datetime.my_trigger",
            "datetime": str(past.replace(tzinfo=None)),
        },
        blocking=True,
    )
    assert len(service_calls) == 1
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "time", "at": "input_datetime.my_trigger"},
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": "{{ trigger.platform }}-{{ trigger.now.day }}-{{ trigger.now.hour }}-{{trigger.entity_id}}"
                    },
                },
            }
        },
    )

    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    assert len(service_calls) == 1

    await hass.services.async_call(
        "input_datetime",
        "set_datetime",
        {
            ATTR_ENTITY_ID: "input_datetime.my_trigger",
            "datetime": str(future.replace(tzinfo=None)),
        },
        blocking=True,
    )
    assert len(service_calls) == 2
    await hass.async_block_till_done()

    async_fire_time_changed(hass, future + timedelta(seconds=1))
    await hass.async_block_till_done()

    assert len(service_calls) == 3
    assert (
        service_calls[2].data["some"]
        == f"time-{future.day}-{future.hour}-input_datetime.my_trigger"
    )
