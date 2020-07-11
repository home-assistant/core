"""The tests for the time automation."""
from datetime import timedelta

import pytest

import homeassistant.components.automation as automation
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import (
    assert_setup_component,
    async_fire_time_changed,
    async_mock_service,
    mock_component,
)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, "group")


async def test_if_fires_using_at(hass, calls):
    """Test for firing at."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "time", "at": "5:00:00"},
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": "{{ trigger.platform }} - {{ trigger.now.hour }}"
                    },
                },
            }
        },
    )

    async_fire_time_changed(hass, dt_util.utcnow().replace(hour=5, minute=0, second=0))

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "time - 5"


async def test_if_not_fires_using_wrong_at(hass, calls):
    """YAML translates time values to total seconds.

    This should break the before rule.
    """
    with assert_setup_component(0, automation.DOMAIN):
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

    async_fire_time_changed(hass, dt_util.utcnow().replace(hour=1, minute=0, second=5))

    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_if_action_before(hass, calls):
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

    before_10 = dt_util.now().replace(hour=8)
    after_10 = dt_util.now().replace(hour=14)

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=before_10):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 1

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=after_10):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 1


async def test_if_action_after(hass, calls):
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

    before_10 = dt_util.now().replace(hour=8)
    after_10 = dt_util.now().replace(hour=14)

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=before_10):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 0

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=after_10):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 1


async def test_if_action_one_weekday(hass, calls):
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

    days_past_monday = dt_util.now().weekday()
    monday = dt_util.now() - timedelta(days=days_past_monday)
    tuesday = monday + timedelta(days=1)

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=monday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 1

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=tuesday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 1


async def test_if_action_list_weekday(hass, calls):
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

    days_past_monday = dt_util.now().weekday()
    monday = dt_util.now() - timedelta(days=days_past_monday)
    tuesday = monday + timedelta(days=1)
    wednesday = tuesday + timedelta(days=1)

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=monday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 1

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=tuesday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 2

    with patch("homeassistant.helpers.condition.dt_util.now", return_value=wednesday):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()

    assert len(calls) == 2
