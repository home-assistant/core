"""The tests for the sun automation."""
from datetime import datetime
from unittest.mock import patch

import pytest

from homeassistant.components import sun
import homeassistant.components.automation as automation
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, async_mock_service, mock_component
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401

ORIG_TIME_ZONE = dt_util.DEFAULT_TIME_ZONE


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, "group")
    dt_util.set_default_time_zone(hass.config.time_zone)
    hass.loop.run_until_complete(
        async_setup_component(hass, sun.DOMAIN, {sun.DOMAIN: {sun.CONF_ELEVATION: 0}})
    )


def teardown():
    """Restore."""
    dt_util.set_default_time_zone(ORIG_TIME_ZONE)


async def test_sunset_trigger(hass, calls, legacy_patchable_time):
    """Test the sunset trigger."""
    now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 2, tzinfo=dt_util.UTC)

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {"platform": "sun", "event": SUN_EVENT_SUNSET},
                    "action": {
                        "service": "test.automation",
                        "data_template": {"id": "{{ trigger.id}}"},
                    },
                }
            },
        )

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert len(calls) == 0

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await hass.services.async_call(
            automation.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
            blocking=True,
        )

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["id"] == 0


async def test_sunrise_trigger(hass, calls, legacy_patchable_time):
    """Test the sunrise trigger."""
    now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 14, tzinfo=dt_util.UTC)

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {"platform": "sun", "event": SUN_EVENT_SUNRISE},
                    "action": {"service": "test.automation"},
                }
            },
        )

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_sunset_trigger_with_offset(hass, calls, legacy_patchable_time):
    """Test the sunset trigger with offset."""
    now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 2, 30, tzinfo=dt_util.UTC)

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "sun",
                        "event": SUN_EVENT_SUNSET,
                        "offset": "0:30:00",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "{{ trigger.%s }}"
                            % "}} - {{ trigger.".join(("platform", "event", "offset"))
                        },
                    },
                }
            },
        )

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "sun - sunset - 0:30:00"


async def test_sunrise_trigger_with_offset(hass, calls, legacy_patchable_time):
    """Test the sunrise trigger with offset."""
    now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 13, 30, tzinfo=dt_util.UTC)

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "sun",
                        "event": SUN_EVENT_SUNRISE,
                        "offset": "-0:30:00",
                    },
                    "action": {"service": "test.automation"},
                }
            },
        )

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert len(calls) == 1


def _find_run_id(traces, trace_type, item_id):
    """Find newest run_id for a script or automation."""
    for trace in reversed(traces):
        if trace["domain"] == trace_type and trace["item_id"] == item_id:
            return trace["run_id"]

    return None


async def assert_automation_condition_trace(hass_ws_client, automation_id, expected):
    """Test the result of automation condition."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    client = await hass_ws_client()

    # List traces
    await client.send_json(
        {"id": next_id(), "type": "trace/list", "domain": "automation"}
    )
    response = await client.receive_json()
    assert response["success"]
    run_id = _find_run_id(response["result"], "automation", automation_id)

    # Get trace
    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/get",
            "domain": "automation",
            "item_id": "sun",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    trace = response["result"]
    assert len(trace["trace"]["condition/0"]) == 1
    condition_trace = trace["trace"]["condition/0"][0]["result"]
    assert condition_trace == expected


async def test_if_action_before_sunrise_no_offset(hass, hass_ws_client, calls):
    """
    Test if action was before sunrise.

    Before sunrise is true from midnight until sunset, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "before": SUN_EVENT_SUNRISE},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise + 1s -> 'before sunrise' not true
    now = datetime(2015, 9, 16, 13, 33, 19, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = sunrise -> 'before sunrise' true
    now = datetime(2015, 9, 16, 13, 33, 18, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = local midnight -> 'before sunrise' true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = local midnight - 1s -> 'before sunrise' not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T13:33:18.342542+00:00"},
    )


async def test_if_action_after_sunrise_no_offset(hass, hass_ws_client, calls):
    """
    Test if action was after sunrise.

    After sunrise is true from sunrise until midnight, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "after": SUN_EVENT_SUNRISE},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise - 1s -> 'after sunrise' not true
    now = datetime(2015, 9, 16, 13, 33, 17, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = sunrise + 1s -> 'after sunrise' true
    now = datetime(2015, 9, 16, 13, 33, 19, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = local midnight -> 'after sunrise' not true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = local midnight - 1s -> 'after sunrise' true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T13:33:18.342542+00:00"},
    )


async def test_if_action_before_sunrise_with_offset(hass, hass_ws_client, calls):
    """
    Test if action was before sunrise with offset.

    Before sunrise is true from midnight until sunset, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "before": SUN_EVENT_SUNRISE,
                    "before_offset": "+1:00:00",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise + 1s + 1h -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 14, 33, 19, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunrise + 1h -> 'before sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 14, 33, 18, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = UTC midnight -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 0, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = UTC midnight - 1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 23, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local midnight -> 'before sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local midnight - 1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunset -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 1, 53, 45, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunset -1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 1, 53, 44, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )


async def test_if_action_before_sunset_with_offset(hass, hass_ws_client, calls):
    """
    Test if action was before sunset with offset.

    Before sunset is true from midnight until sunset, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "before": "sunset",
                    "before_offset": "+1:00:00",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = local midnight -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunset + 1s + 1h -> 'before sunset' with offset +1h not true
    now = datetime(2015, 9, 17, 2, 53, 46, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunset + 1h -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 17, 2, 53, 44, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = UTC midnight -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 17, 0, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 3
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = UTC midnight - 1s -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 23, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 4
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunrise -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 13, 33, 18, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 5
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunrise -1s -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 13, 33, 17, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 6
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = local midnight-1s -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 6
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )


async def test_if_action_after_sunrise_with_offset(hass, hass_ws_client, calls):
    """
    Test if action was after sunrise with offset.

    After sunrise is true from sunrise until midnight, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "after": SUN_EVENT_SUNRISE,
                    "after_offset": "+1:00:00",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise - 1s + 1h -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 14, 33, 17, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunrise + 1h -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 14, 33, 58, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = UTC noon -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 12, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = UTC noon - 1s -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 11, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local noon -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 19, 1, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local noon - 1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 18, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 3
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunset -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 1, 53, 45, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 4
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunset + 1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 1, 53, 45, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 5
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local midnight-1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 6
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local midnight -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 6
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-17T14:33:57.053037+00:00"},
    )


async def test_if_action_after_sunset_with_offset(hass, hass_ws_client, calls):
    """
    Test if action was after sunset with offset.

    After sunset is true from sunset until midnight, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "after": "sunset",
                    "after_offset": "+1:00:00",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunset - 1s + 1h -> 'after sunset' with offset +1h not true
    now = datetime(2015, 9, 17, 2, 53, 44, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunset + 1h -> 'after sunset' with offset +1h true
    now = datetime(2015, 9, 17, 2, 53, 45, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = midnight-1s -> 'after sunset' with offset +1h true
    now = datetime(2015, 9, 16, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T02:55:06.099767+00:00"},
    )

    # now = midnight -> 'after sunset' with offset +1h not true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-17T02:53:44.723614+00:00"},
    )


async def test_if_action_before_and_after_during(hass, hass_ws_client, calls):
    """
    Test if action was after sunset and before sunrise.

    This is true from sunrise until sunset.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "after": SUN_EVENT_SUNRISE,
                    "before": SUN_EVENT_SUNSET,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise - 1s -> 'after sunrise' + 'before sunset' not true
    now = datetime(2015, 9, 16, 13, 33, 17, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": False,
            "wanted_time_before": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_after": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = sunset + 1s -> 'after sunrise' + 'before sunset' not true
    now = datetime(2015, 9, 17, 1, 53, 46, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-17T01:53:44.723614+00:00"},
    )

    # now = sunrise + 1s -> 'after sunrise' + 'before sunset' true
    now = datetime(2015, 9, 16, 13, 33, 19, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_before": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_after": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = sunset - 1s -> 'after sunrise' + 'before sunset' true
    now = datetime(2015, 9, 17, 1, 53, 44, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_before": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_after": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = 9AM local  -> 'after sunrise' + 'before sunset' true
    now = datetime(2015, 9, 16, 16, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 3
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_before": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_after": "2015-09-16T13:33:18.342542+00:00",
        },
    )


async def test_if_action_before_sunrise_no_offset_kotzebue(hass, hass_ws_client, calls):
    """
    Test if action was before sunrise.

    Local timezone: Alaska time
    Location: Kotzebue, which has a very skewed local timezone with sunrise
    at 7 AM and sunset at 3AM during summer
    After sunrise is true from sunrise until midnight, local time.
    """
    tz = dt_util.get_time_zone("America/Anchorage")
    dt_util.set_default_time_zone(tz)
    hass.config.latitude = 66.5
    hass.config.longitude = 162.4
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "before": SUN_EVENT_SUNRISE},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:21:12 local, sunset: 2015-07-25 03:13:33 local
    # sunrise: 2015-07-24 15:21:12 UTC,   sunset: 2015-07-25 11:13:33 UTC
    # now = sunrise + 1s -> 'before sunrise' not true
    now = datetime(2015, 7, 24, 15, 21, 13, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = sunrise - 1h -> 'before sunrise' true
    now = datetime(2015, 7, 24, 14, 21, 12, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = local midnight -> 'before sunrise' true
    now = datetime(2015, 7, 24, 8, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = local midnight - 1s -> 'before sunrise' not true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-07-23T15:12:19.155123+00:00"},
    )


async def test_if_action_after_sunrise_no_offset_kotzebue(hass, hass_ws_client, calls):
    """
    Test if action was after sunrise.

    Local timezone: Alaska time
    Location: Kotzebue, which has a very skewed local timezone with sunrise
    at 7 AM and sunset at 3AM during summer
    Before sunrise is true from midnight until sunrise, local time.
    """
    tz = dt_util.get_time_zone("America/Anchorage")
    dt_util.set_default_time_zone(tz)
    hass.config.latitude = 66.5
    hass.config.longitude = 162.4
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "after": SUN_EVENT_SUNRISE},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:21:12 local, sunset: 2015-07-25 03:13:33 local
    # sunrise: 2015-07-24 15:21:12 UTC,   sunset: 2015-07-25 11:13:33 UTC
    # now = sunrise -> 'after sunrise' true
    now = datetime(2015, 7, 24, 15, 21, 12, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = sunrise - 1h -> 'after sunrise' not true
    now = datetime(2015, 7, 24, 14, 21, 12, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = local midnight -> 'after sunrise' not true
    now = datetime(2015, 7, 24, 8, 0, 1, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = local midnight - 1s -> 'after sunrise' true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-07-23T15:12:19.155123+00:00"},
    )


async def test_if_action_before_sunset_no_offset_kotzebue(hass, hass_ws_client, calls):
    """
    Test if action was before sunrise.

    Local timezone: Alaska time
    Location: Kotzebue, which has a very skewed local timezone with sunrise
    at 7 AM and sunset at 3AM during summer
    Before sunset is true from midnight until sunset, local time.
    """
    tz = dt_util.get_time_zone("America/Anchorage")
    dt_util.set_default_time_zone(tz)
    hass.config.latitude = 66.5
    hass.config.longitude = 162.4
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "before": SUN_EVENT_SUNSET},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:21:12 local, sunset: 2015-07-25 03:13:33 local
    # sunrise: 2015-07-24 15:21:12 UTC,   sunset: 2015-07-25 11:13:33 UTC
    # now = sunset + 1s -> 'before sunset' not true
    now = datetime(2015, 7, 25, 11, 13, 34, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-07-25T11:13:32.501837+00:00"},
    )

    # now = sunset - 1h-> 'before sunset' true
    now = datetime(2015, 7, 25, 10, 13, 33, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-07-25T11:13:32.501837+00:00"},
    )

    # now = local midnight -> 'before sunrise' true
    now = datetime(2015, 7, 24, 8, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-07-24T11:17:54.446913+00:00"},
    )

    # now = local midnight - 1s -> 'before sunrise' not true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-07-23T11:22:18.467277+00:00"},
    )


async def test_if_action_after_sunset_no_offset_kotzebue(hass, hass_ws_client, calls):
    """
    Test if action was after sunrise.

    Local timezone: Alaska time
    Location: Kotzebue, which has a very skewed local timezone with sunrise
    at 7 AM and sunset at 3AM during summer
    After sunset is true from sunset until midnight, local time.
    """
    tz = dt_util.get_time_zone("America/Anchorage")
    dt_util.set_default_time_zone(tz)
    hass.config.latitude = 66.5
    hass.config.longitude = 162.4
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "after": SUN_EVENT_SUNSET},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:21:12 local, sunset: 2015-07-25 03:13:33 local
    # sunrise: 2015-07-24 15:21:12 UTC,   sunset: 2015-07-25 11:13:33 UTC
    # now = sunset -> 'after sunset' true
    now = datetime(2015, 7, 25, 11, 13, 33, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-07-25T11:13:32.501837+00:00"},
    )

    # now = sunset - 1s -> 'after sunset' not true
    now = datetime(2015, 7, 25, 11, 13, 32, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-07-25T11:13:32.501837+00:00"},
    )

    # now = local midnight -> 'after sunset' not true
    now = datetime(2015, 7, 24, 8, 0, 1, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-07-24T11:17:54.446913+00:00"},
    )

    # now = local midnight - 1s -> 'after sunset' true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-07-23T11:22:18.467277+00:00"},
    )
