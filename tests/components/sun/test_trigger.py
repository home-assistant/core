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
