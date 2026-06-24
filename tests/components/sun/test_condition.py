"""The tests for sun conditions."""

from datetime import datetime

from freezegun import freeze_time
import pytest
import voluptuous as vol

from homeassistant.components import automation
from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import trace
from homeassistant.helpers.condition import async_validate_condition_config
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.typing import WebSocketGenerator

# San Diego (default test location) and Longyearbyen, Svalbard (deep polar).
_SAN_DIEGO = (32.87336, -117.22743, "US/Pacific")
_SVALBARD = (78.22, 15.65, "Europe/Oslo")

_TWILIGHT_TYPES = ("any", "civil", "nautical", "astronomical")


@pytest.fixture(autouse=True)
def prepare_condition_trace() -> None:
    """Clear previous trace."""
    trace.trace_clear()


def _find_run_id(traces, trace_type, item_id):
    """Find newest run_id for a script or automation."""
    for _trace in reversed(traces):
        if _trace["domain"] == trace_type and _trace["item_id"] == item_id:
            return _trace["run_id"]

    return None


async def assert_automation_condition_trace(hass_ws_client, automation_id, expected):
    """Test the result of automation condition."""
    msg_id = 1

    def next_id():
        nonlocal msg_id
        msg_id += 1
        return msg_id

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


async def test_if_action_before_sunrise_no_offset(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was before sunrise.

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
                    "options": {"before": SUN_EVENT_SUNRISE},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise + 1s -> 'before sunrise' not true
    now = datetime(2015, 9, 16, 13, 33, 19, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = sunrise -> 'before sunrise' true
    now = datetime(2015, 9, 16, 13, 33, 18, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = local midnight -> 'before sunrise' true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = local midnight - 1s -> 'before sunrise' not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T13:33:18.342542+00:00"},
    )


async def test_if_action_after_sunrise_no_offset(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was after sunrise.

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
                    "options": {"after": SUN_EVENT_SUNRISE},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise - 1s -> 'after sunrise' not true
    now = datetime(2015, 9, 16, 13, 33, 17, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = sunrise + 1s -> 'after sunrise' true
    now = datetime(2015, 9, 16, 13, 33, 19, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = local midnight -> 'after sunrise' not true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T13:33:18.342542+00:00"},
    )

    # now = local midnight - 1s -> 'after sunrise' true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T13:33:18.342542+00:00"},
    )


async def test_if_action_before_sunrise_with_offset(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was before sunrise with offset.

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
                    "options": {
                        "before": SUN_EVENT_SUNRISE,
                        "before_offset": "+1:00:00",
                    },
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise + 1s + 1h -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 14, 33, 19, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunrise + 1h -> 'before sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 14, 33, 18, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = UTC midnight -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 0, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = UTC midnight - 1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 23, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local midnight -> 'before sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local midnight - 1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunset -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 1, 53, 45, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunset -1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 1, 53, 44, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-16T14:33:18.342542+00:00"},
    )


async def test_if_action_before_sunset_with_offset(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was before sunset with offset.

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
                    "options": {"before": "sunset", "before_offset": "+1:00:00"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = local midnight -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunset + 1s + 1h -> 'before sunset' with offset +1h not true
    now = datetime(2015, 9, 17, 2, 53, 46, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunset + 1h -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 17, 2, 53, 44, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = UTC midnight -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 17, 0, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 3
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = UTC midnight - 1s -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 23, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 4
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunrise -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 13, 33, 18, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 5
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunrise -1s -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 13, 33, 17, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 6
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = local midnight-1s -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 6
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-17T02:53:44.723614+00:00"},
    )


async def test_if_action_after_sunrise_with_offset(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was after sunrise with offset.

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
                    "options": {"after": SUN_EVENT_SUNRISE, "after_offset": "+1:00:00"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise - 1s + 1h -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 14, 33, 17, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunrise + 1h -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 14, 33, 58, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = UTC noon -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 12, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = UTC noon - 1s -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 11, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local noon -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 19, 1, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local noon - 1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 18, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 3
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunset -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 1, 53, 45, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 4
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = sunset + 1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 1, 53, 45, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 5
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local midnight-1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 6
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T14:33:18.342542+00:00"},
    )

    # now = local midnight -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 7, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 6
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-17T14:33:57.053037+00:00"},
    )


async def test_if_action_after_sunset_with_offset(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was after sunset with offset.

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
                    "options": {"after": "sunset", "after_offset": "+1:00:00"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunset - 1s + 1h -> 'after sunset' with offset +1h not true
    now = datetime(2015, 9, 17, 2, 53, 44, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = sunset + 1h -> 'after sunset' with offset +1h true
    now = datetime(2015, 9, 17, 2, 53, 45, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-17T02:53:44.723614+00:00"},
    )

    # now = midnight-1s -> 'after sunset' with offset +1h true
    now = datetime(2015, 9, 16, 6, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-09-16T02:55:06.099767+00:00"},
    )

    # now = midnight -> 'after sunset' with offset +1h not true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-09-17T02:53:44.723614+00:00"},
    )


async def test_if_action_after_and_before_during(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was after sunrise and before sunset.

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
                    "options": {"after": SUN_EVENT_SUNRISE, "before": SUN_EVENT_SUNSET},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise - 1s -> 'after sunrise' + 'before sunset' not true
    now = datetime(2015, 9, 16, 13, 33, 17, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
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
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-09-17T01:53:44.723614+00:00"},
    )

    # now = sunrise + 1s -> 'after sunrise' + 'before sunset' true
    now = datetime(2015, 9, 16, 13, 33, 19, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
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
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
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
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 3
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_before": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_after": "2015-09-16T13:33:18.342542+00:00",
        },
    )


async def test_if_action_before_or_after_during(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was before sunrise or after sunset.

    This is true from midnight until sunrise and from sunset until midnight
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
                    "options": {"before": SUN_EVENT_SUNRISE, "after": SUN_EVENT_SUNSET},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:33:18 local, sunset: 2015-09-16 18:53:45 local
    # sunrise: 2015-09-16 13:33:18 UTC,   sunset: 2015-09-17 01:53:45 UTC
    # now = sunrise - 1s -> 'before sunrise' | 'after sunset' true
    now = datetime(2015, 9, 16, 13, 33, 17, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_after": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_before": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = sunset + 1s -> 'before sunrise' | 'after sunset' true
    now = datetime(2015, 9, 17, 1, 53, 46, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_after": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_before": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = sunrise + 1s -> 'before sunrise' | 'after sunset' false
    now = datetime(2015, 9, 16, 13, 33, 19, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": False,
            "wanted_time_after": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_before": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = sunset - 1s -> 'before sunrise' | 'after sunset' false
    now = datetime(2015, 9, 17, 1, 53, 44, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": False,
            "wanted_time_after": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_before": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = midnight + 1s local  -> 'before sunrise' | 'after sunset' true
    now = datetime(2015, 9, 16, 7, 0, 1, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 3
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_after": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_before": "2015-09-16T13:33:18.342542+00:00",
        },
    )

    # now = midnight - 1s local  -> 'before sunrise' | 'after sunset' true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 4
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {
            "result": True,
            "wanted_time_after": "2015-09-17T01:53:44.723614+00:00",
            "wanted_time_before": "2015-09-16T13:33:18.342542+00:00",
        },
    )


async def test_if_action_before_sunrise_no_offset_kotzebue(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was before sunrise.

    Local timezone: Alaska time
    Location: Kotzebue, which has a very skewed local timezone with sunrise
    at 7 AM and sunset at 3AM during summer
    After sunrise is true from sunrise until midnight, local time.
    """
    await hass.config.async_set_time_zone("America/Anchorage")
    hass.config.latitude = 66.5
    hass.config.longitude = 162.4
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "options": {"before": SUN_EVENT_SUNRISE},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:21:12 local, sunset: 2015-07-25 03:13:33 local
    # sunrise: 2015-07-24 15:21:12 UTC,   sunset: 2015-07-25 11:13:33 UTC
    # now = sunrise + 1s -> 'before sunrise' not true
    now = datetime(2015, 7, 24, 15, 21, 13, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = sunrise - 1h -> 'before sunrise' true
    now = datetime(2015, 7, 24, 14, 21, 12, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = local midnight -> 'before sunrise' true
    now = datetime(2015, 7, 24, 8, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = local midnight - 1s -> 'before sunrise' not true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-07-23T15:12:19.155123+00:00"},
    )


async def test_if_action_after_sunrise_no_offset_kotzebue(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was after sunrise.

    Local timezone: Alaska time
    Location: Kotzebue, which has a very skewed local timezone with sunrise
    at 7 AM and sunset at 3AM during summer
    Before sunrise is true from midnight until sunrise, local time.
    """
    await hass.config.async_set_time_zone("America/Anchorage")
    hass.config.latitude = 66.5
    hass.config.longitude = 162.4
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "options": {"after": SUN_EVENT_SUNRISE},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:21:12 local, sunset: 2015-07-25 03:13:33 local
    # sunrise: 2015-07-24 15:21:12 UTC,   sunset: 2015-07-25 11:13:33 UTC
    # now = sunrise -> 'after sunrise' true
    now = datetime(2015, 7, 24, 15, 21, 12, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = sunrise - 1h -> 'after sunrise' not true
    now = datetime(2015, 7, 24, 14, 21, 12, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = local midnight -> 'after sunrise' not true
    now = datetime(2015, 7, 24, 8, 0, 1, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-07-24T15:16:46.975735+00:00"},
    )

    # now = local midnight - 1s -> 'after sunrise' true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-07-23T15:12:19.155123+00:00"},
    )


async def test_if_action_before_sunset_no_offset_kotzebue(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was before sunrise.

    Local timezone: Alaska time
    Location: Kotzebue, which has a very skewed local timezone with sunrise
    at 7 AM and sunset at 3AM during summer
    Before sunset is true from midnight until sunset, local time.
    """
    await hass.config.async_set_time_zone("America/Anchorage")
    hass.config.latitude = 66.5
    hass.config.longitude = 162.4
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "options": {"before": SUN_EVENT_SUNSET},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:21:12 local, sunset: 2015-07-25 03:13:33 local
    # sunrise: 2015-07-24 15:21:12 UTC,   sunset: 2015-07-25 11:13:33 UTC
    # now = sunset + 1s -> 'before sunset' not true
    now = datetime(2015, 7, 25, 11, 13, 34, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 0
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-07-25T11:13:32.501837+00:00"},
    )

    # now = sunset - 1h-> 'before sunset' true
    now = datetime(2015, 7, 25, 10, 13, 33, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-07-25T11:13:32.501837+00:00"},
    )

    # now = local midnight -> 'before sunrise' true
    now = datetime(2015, 7, 24, 8, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_before": "2015-07-24T11:17:54.446913+00:00"},
    )

    # now = local midnight - 1s -> 'before sunrise' not true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_before": "2015-07-23T11:22:18.467277+00:00"},
    )


async def test_if_action_after_sunset_no_offset_kotzebue(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service_calls: list[ServiceCall],
) -> None:
    """Test if action was after sunrise.

    Local timezone: Alaska time
    Location: Kotzebue, which has a very skewed local timezone with sunrise
    at 7 AM and sunset at 3AM during summer
    After sunset is true from sunset until midnight, local time.
    """
    await hass.config.async_set_time_zone("America/Anchorage")
    hass.config.latitude = 66.5
    hass.config.longitude = 162.4
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun",
                    "options": {"after": SUN_EVENT_SUNSET},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:21:12 local, sunset: 2015-07-25 03:13:33 local
    # sunrise: 2015-07-24 15:21:12 UTC,   sunset: 2015-07-25 11:13:33 UTC
    # now = sunset -> 'after sunset' true
    now = datetime(2015, 7, 25, 11, 13, 33, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-07-25T11:13:32.501837+00:00"},
    )

    # now = sunset - 1s -> 'after sunset' not true
    now = datetime(2015, 7, 25, 11, 13, 32, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-07-25T11:13:32.501837+00:00"},
    )

    # now = local midnight -> 'after sunset' not true
    now = datetime(2015, 7, 24, 8, 0, 1, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 1
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": False, "wanted_time_after": "2015-07-24T11:17:54.446913+00:00"},
    )

    # now = local midnight - 1s -> 'after sunset' true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(service_calls) == 2
    await assert_automation_condition_trace(
        hass_ws_client,
        "sun",
        {"result": True, "wanted_time_after": "2015-07-23T11:22:18.467277+00:00"},
    )


@pytest.mark.parametrize(
    ("condition_key", "location", "now", "expected"),
    [
        # San Diego, just after solar noon (sun high, descending).
        (
            "sun.is_up",
            _SAN_DIEGO,
            datetime(2015, 9, 15, 20, tzinfo=dt_util.UTC),
            True,
        ),
        (
            "sun.is_set",
            _SAN_DIEGO,
            datetime(2015, 9, 15, 20, tzinfo=dt_util.UTC),
            False,
        ),
        (
            "sun.is_descending",
            _SAN_DIEGO,
            datetime(2015, 9, 15, 20, tzinfo=dt_util.UTC),
            True,
        ),
        (
            "sun.is_ascending",
            _SAN_DIEGO,
            datetime(2015, 9, 15, 20, tzinfo=dt_util.UTC),
            False,
        ),
        (
            "sun.is_night",
            _SAN_DIEGO,
            datetime(2015, 9, 15, 20, tzinfo=dt_util.UTC),
            False,
        ),
        # San Diego, just before solar noon (sun high, rising).
        (
            "sun.is_ascending",
            _SAN_DIEGO,
            datetime(2015, 9, 15, 19, tzinfo=dt_util.UTC),
            True,
        ),
        (
            "sun.is_descending",
            _SAN_DIEGO,
            datetime(2015, 9, 15, 19, tzinfo=dt_util.UTC),
            False,
        ),
        # San Diego, deep night.
        (
            "sun.is_set",
            _SAN_DIEGO,
            datetime(2015, 9, 15, 8, 30, tzinfo=dt_util.UTC),
            True,
        ),
        (
            "sun.is_up",
            _SAN_DIEGO,
            datetime(2015, 9, 15, 8, 30, tzinfo=dt_util.UTC),
            False,
        ),
        (
            "sun.is_night",
            _SAN_DIEGO,
            datetime(2015, 9, 15, 8, 30, tzinfo=dt_util.UTC),
            True,
        ),
        # Svalbard: above the horizon during midnight sun (June), below during
        # polar night (December).
        (
            "sun.is_up",
            _SVALBARD,
            datetime(2015, 6, 15, 12, tzinfo=dt_util.UTC),
            True,
        ),
        (
            "sun.is_set",
            _SVALBARD,
            datetime(2015, 12, 15, 12, tzinfo=dt_util.UTC),
            True,
        ),
    ],
)
async def test_sun_state_conditions(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    condition_key: str,
    location: tuple[float, float, str],
    now: datetime,
    expected: bool,
) -> None:
    """Test the option-less sun state conditions evaluate from the sun position."""
    latitude, longitude, time_zone = location
    await hass.config.async_set_time_zone(time_zone)
    hass.config.latitude = latitude
    hass.config.longitude = longitude
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": condition_key},
                "action": {"service": "test.automation"},
            }
        },
    )

    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert bool(service_calls) is expected


@pytest.mark.parametrize(
    "condition_key",
    [
        "sun.is_up",
        "sun.is_set",
        "sun.is_ascending",
        "sun.is_descending",
        "sun.is_night",
    ],
)
async def test_sun_state_condition_takes_no_options(
    hass: HomeAssistant, condition_key: str
) -> None:
    """Test the sun state conditions accept no target and reject options."""
    await async_validate_condition_config(hass, {"condition": condition_key})
    with pytest.raises(vol.Invalid):
        await async_validate_condition_config(
            hass, {"condition": condition_key, "options": {"unknown": True}}
        )


@pytest.mark.parametrize(
    ("threshold", "elevation", "expected"),
    [
        ({"type": "above", "value": {"number": 10}}, 15.0, True),
        ({"type": "above", "value": {"number": 10}}, 5.0, False),
        ({"type": "below", "value": {"number": 0}}, -5.0, True),
        ({"type": "below", "value": {"number": 0}}, 5.0, False),
        # Negative thresholds (sun below the horizon) are valid.
        ({"type": "below", "value": {"number": -6}}, -10.0, True),
        (
            {
                "type": "between",
                "value_min": {"number": -6},
                "value_max": {"number": 6},
            },
            0.0,
            True,
        ),
        (
            {
                "type": "between",
                "value_min": {"number": -6},
                "value_max": {"number": 6},
            },
            10.0,
            False,
        ),
    ],
)
async def test_elevation_condition(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    threshold: dict[str, object],
    elevation: float,
    expected: bool,
) -> None:
    """Test the elevation condition compares the sun's elevation to a threshold."""
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": elevation})
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "sun.elevation",
                    "options": {"threshold": threshold},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    assert bool(service_calls) is expected


@pytest.mark.parametrize(
    ("condition_key", "now", "expected_true"),
    [
        # San Diego morning twilight (rising). The twilight bands are mutually
        # exclusive, so at each elevation exactly one specific band matches (plus
        # "any" whenever the sun is in any twilight band at all).
        # 13:15Z ~ -4.4° (civil band).
        (
            "sun.is_morning_twilight",
            datetime(2015, 9, 15, 13, 15, tzinfo=dt_util.UTC),
            {"any", "civil"},
        ),
        # 13:00Z ~ -7.6° (nautical band).
        (
            "sun.is_morning_twilight",
            datetime(2015, 9, 15, 13, 0, tzinfo=dt_util.UTC),
            {"any", "nautical"},
        ),
        # 12:30Z ~ -13.8° (astronomical band).
        (
            "sun.is_morning_twilight",
            datetime(2015, 9, 15, 12, 30, tzinfo=dt_util.UTC),
            {"any", "astronomical"},
        ),
        # 12:00Z ~ -19.8° (night, below all twilight bands).
        (
            "sun.is_morning_twilight",
            datetime(2015, 9, 15, 12, 0, tzinfo=dt_util.UTC),
            set(),
        ),
        # Morning twilight requires the sun to be rising; an evening (descending)
        # time matches no type.
        (
            "sun.is_morning_twilight",
            datetime(2015, 9, 16, 2, 45, tzinfo=dt_util.UTC),
            set(),
        ),
        # San Diego evening twilight (descending).
        # 02:15Z ~ -4.9° (civil band).
        (
            "sun.is_evening_twilight",
            datetime(2015, 9, 16, 2, 15, tzinfo=dt_util.UTC),
            {"any", "civil"},
        ),
        # 02:45Z ~ -11.2° (nautical band).
        (
            "sun.is_evening_twilight",
            datetime(2015, 9, 16, 2, 45, tzinfo=dt_util.UTC),
            {"any", "nautical"},
        ),
        # 03:15Z ~ -17.3° (astronomical band).
        (
            "sun.is_evening_twilight",
            datetime(2015, 9, 16, 3, 15, tzinfo=dt_util.UTC),
            {"any", "astronomical"},
        ),
        # Evening twilight requires the sun to be descending; a morning (rising)
        # time matches no type.
        (
            "sun.is_evening_twilight",
            datetime(2015, 9, 15, 13, 0, tzinfo=dt_util.UTC),
            set(),
        ),
    ],
)
async def test_twilight_condition_type(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    condition_key: str,
    now: datetime,
    expected_true: set[str],
) -> None:
    """Test the morning/evening twilight conditions honor the twilight type band.

    At a single point in time every twilight type is checked, so the mutually
    exclusive bands are all asserted together.
    """
    latitude, longitude, time_zone = _SAN_DIEGO
    await hass.config.async_set_time_zone(time_zone)
    hass.config.latitude = latitude
    hass.config.longitude = longitude
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "condition": {
                        "condition": condition_key,
                        "options": {"type": twilight_type},
                    },
                    "action": {
                        "service": "test.automation",
                        "data": {"type": twilight_type},
                    },
                }
                for twilight_type in _TWILIGHT_TYPES
            ]
        },
    )

    with freeze_time(now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert {call.data["type"] for call in service_calls} == expected_true
