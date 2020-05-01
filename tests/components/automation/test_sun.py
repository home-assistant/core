"""The tests for the sun automation."""
from datetime import datetime
from unittest.mock import patch

import pytest

from homeassistant.components import sun
import homeassistant.components.automation as automation
from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, async_mock_service, mock_component
from tests.components.automation import common

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


async def test_sunset_trigger(hass, calls):
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
                    "action": {"service": "test.automation"},
                }
            },
        )

    await common.async_turn_off(hass)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert len(calls) == 0

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await common.async_turn_on(hass)
        await hass.async_block_till_done()

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_sunrise_trigger(hass, calls):
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


async def test_sunset_trigger_with_offset(hass, calls):
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


async def test_sunrise_trigger_with_offset(hass, calls):
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


async def test_if_action_before_sunrise_no_offset(hass, calls):
    """
    Test if action was before sunrise.

    Before sunrise is true from midnight until sunset, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "before": SUN_EVENT_SUNRISE},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:32:43 local, sunset: 2015-09-16 18:55:24 local
    # sunrise: 2015-09-16 13:32:43 UTC,   sunset: 2015-09-17 01:55:24 UTC
    # now = sunrise + 1s -> 'before sunrise' not true
    now = datetime(2015, 9, 16, 13, 32, 44, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0

    # now = sunrise -> 'before sunrise' true
    now = datetime(2015, 9, 16, 13, 32, 43, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = local midnight -> 'before sunrise' true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2

    # now = local midnight - 1s -> 'before sunrise' not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2


async def test_if_action_after_sunrise_no_offset(hass, calls):
    """
    Test if action was after sunrise.

    After sunrise is true from sunrise until midnight, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "after": SUN_EVENT_SUNRISE},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-09-16 06:32:43 local, sunset: 2015-09-16 18:55:24 local
    # sunrise: 2015-09-16 13:32:43 UTC,   sunset: 2015-09-17 01:55:24 UTC
    # now = sunrise - 1s -> 'after sunrise' not true
    now = datetime(2015, 9, 16, 13, 32, 42, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0

    # now = sunrise + 1s -> 'after sunrise' true
    now = datetime(2015, 9, 16, 13, 32, 43, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = local midnight -> 'after sunrise' not true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = local midnight - 1s -> 'after sunrise' true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2


async def test_if_action_before_sunrise_with_offset(hass, calls):
    """
    Test if action was before sunrise with offset.

    Before sunrise is true from midnight until sunset, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
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

    # sunrise: 2015-09-16 06:32:43 local, sunset: 2015-09-16 18:55:24 local
    # sunrise: 2015-09-16 13:32:43 UTC,   sunset: 2015-09-17 01:55:24 UTC
    # now = sunrise + 1s + 1h -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 14, 32, 44, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0

    # now = sunrise + 1h -> 'before sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 14, 32, 43, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = UTC midnight -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 0, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = UTC midnight - 1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 23, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = local midnight -> 'before sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2

    # now = local midnight - 1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2

    # now = sunset -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 1, 56, 48, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2

    # now = sunset -1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 1, 56, 45, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2


async def test_if_action_before_sunset_with_offset(hass, calls):
    """
    Test if action was before sunset with offset.

    Before sunset is true from midnight until sunset, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
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

    # sunrise: 2015-09-16 06:32:43 local, sunset: 2015-09-16 18:55:24 local
    # sunrise: 2015-09-16 13:32:43 UTC,   sunset: 2015-09-17 01:55:24 UTC
    # now = local midnight -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = sunset + 1s + 1h -> 'before sunset' with offset +1h not true
    now = datetime(2015, 9, 17, 2, 55, 25, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = sunset + 1h -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 17, 2, 55, 24, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2

    # now = UTC midnight -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 17, 0, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 3

    # now = UTC midnight - 1s -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 23, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 4

    # now = sunrise -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 13, 32, 43, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 5

    # now = sunrise -1s -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 13, 32, 42, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 6

    # now = local midnight-1s -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 6


async def test_if_action_after_sunrise_with_offset(hass, calls):
    """
    Test if action was after sunrise with offset.

    After sunrise is true from sunrise until midnight, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
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

    # sunrise: 2015-09-16 06:32:43 local, sunset: 2015-09-16 18:55:24 local
    # sunrise: 2015-09-16 13:32:43 UTC,   sunset: 2015-09-17 01:55:24 UTC
    # now = sunrise - 1s + 1h -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 14, 32, 42, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0

    # now = sunrise + 1h -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 14, 32, 43, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = UTC noon -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 12, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = UTC noon - 1s -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 11, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = local noon -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 19, 1, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2

    # now = local noon - 1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 18, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 3

    # now = sunset -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 1, 55, 24, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 4

    # now = sunset + 1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 1, 55, 25, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 5

    # now = local midnight-1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 6

    # now = local midnight -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 6


async def test_if_action_after_sunset_with_offset(hass, calls):
    """
    Test if action was after sunset with offset.

    After sunset is true from sunset until midnight, local time.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
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

    # sunrise: 2015-09-15 06:32:05 local, sunset: 2015-09-15 18:56:46 local
    # sunrise: 2015-09-15 13:32:05 UTC,   sunset: 2015-09-16 01:56:46 UTC
    # now = sunset - 1s + 1h -> 'after sunset' with offset +1h not true
    now = datetime(2015, 9, 16, 2, 56, 45, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0

    # now = sunset + 1h -> 'after sunset' with offset +1h true
    now = datetime(2015, 9, 16, 2, 56, 46, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = midnight-1s -> 'after sunset' with offset +1h true
    now = datetime(2015, 9, 16, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2

    # now = midnight -> 'after sunset' with offset +1h not true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2


async def test_if_action_before_and_after_during(hass, calls):
    """
    Test if action was after sunset and before sunrise.

    This is true from sunrise until sunset.
    """
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
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

    # sunrise: 2015-09-16 06:32:43 local, sunset: 2015-09-16 18:55:24 local
    # sunrise: 2015-09-16 13:32:43 UTC,   sunset: 2015-09-17 01:55:24 UTC
    # now = sunrise - 1s -> 'after sunrise' + 'before sunset' not true
    now = datetime(2015, 9, 16, 13, 32, 42, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0

    # now = sunset + 1s -> 'after sunrise' + 'before sunset' not true
    now = datetime(2015, 9, 17, 1, 55, 25, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0

    # now = sunrise -> 'after sunrise' + 'before sunset' true
    now = datetime(2015, 9, 16, 13, 32, 43, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = sunset -> 'after sunrise' + 'before sunset' true
    now = datetime(2015, 9, 17, 1, 55, 24, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2

    # now = 9AM local  -> 'after sunrise' + 'before sunset' true
    now = datetime(2015, 9, 16, 16, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 3


async def test_if_action_before_sunrise_no_offset_kotzebue(hass, calls):
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
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "before": SUN_EVENT_SUNRISE},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:17:24 local, sunset: 2015-07-25 03:16:27 local
    # sunrise: 2015-07-24 15:17:24 UTC,   sunset: 2015-07-25 11:16:27 UTC
    # now = sunrise + 1s -> 'before sunrise' not true
    now = datetime(2015, 7, 24, 15, 17, 25, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0

    # now = sunrise -> 'before sunrise' true
    now = datetime(2015, 7, 24, 15, 17, 24, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = local midnight -> 'before sunrise' true
    now = datetime(2015, 7, 24, 8, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2

    # now = local midnight - 1s -> 'before sunrise' not true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2


async def test_if_action_after_sunrise_no_offset_kotzebue(hass, calls):
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
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "after": SUN_EVENT_SUNRISE},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:17:24 local, sunset: 2015-07-25 03:16:27 local
    # sunrise: 2015-07-24 15:17:24 UTC,   sunset: 2015-07-25 11:16:27 UTC
    # now = sunrise -> 'after sunrise' true
    now = datetime(2015, 7, 24, 15, 17, 24, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = sunrise - 1s -> 'after sunrise' not true
    now = datetime(2015, 7, 24, 15, 17, 23, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = local midnight -> 'after sunrise' not true
    now = datetime(2015, 7, 24, 8, 0, 1, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = local midnight - 1s -> 'after sunrise' true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2


async def test_if_action_before_sunset_no_offset_kotzebue(hass, calls):
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
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "before": SUN_EVENT_SUNSET},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:17:24 local, sunset: 2015-07-25 03:16:27 local
    # sunrise: 2015-07-24 15:17:24 UTC,   sunset: 2015-07-25 11:16:27 UTC
    # now = sunrise + 1s -> 'before sunrise' not true
    now = datetime(2015, 7, 25, 11, 16, 28, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 0

    # now = sunrise -> 'before sunrise' true
    now = datetime(2015, 7, 25, 11, 16, 27, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = local midnight -> 'before sunrise' true
    now = datetime(2015, 7, 24, 8, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2

    # now = local midnight - 1s -> 'before sunrise' not true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2


async def test_if_action_after_sunset_no_offset_kotzebue(hass, calls):
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
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {"condition": "sun", "after": SUN_EVENT_SUNSET},
                "action": {"service": "test.automation"},
            }
        },
    )

    # sunrise: 2015-07-24 07:17:24 local, sunset: 2015-07-25 03:16:27 local
    # sunrise: 2015-07-24 15:17:24 UTC,   sunset: 2015-07-25 11:16:27 UTC
    # now = sunset -> 'after sunset' true
    now = datetime(2015, 7, 25, 11, 16, 27, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = sunset - 1s -> 'after sunset' not true
    now = datetime(2015, 7, 25, 11, 16, 26, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = local midnight -> 'after sunset' not true
    now = datetime(2015, 7, 24, 8, 0, 1, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 1

    # now = local midnight - 1s -> 'after sunset' true
    now = datetime(2015, 7, 24, 7, 59, 59, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()
        assert len(calls) == 2
