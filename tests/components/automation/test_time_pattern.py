"""The tests for the time_pattern automation."""
import pytest

import homeassistant.components.automation as automation
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, async_mock_service, mock_component
from tests.components.automation import common


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, "group")


async def test_if_fires_when_hour_matches(hass, calls):
    """Test for firing if hour is matching."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "time_pattern",
                    "hours": 0,
                    "minutes": "*",
                    "seconds": "*",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_time_changed(hass, dt_util.utcnow().replace(hour=0))
    await hass.async_block_till_done()
    assert len(calls) == 1

    await common.async_turn_off(hass)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow().replace(hour=0))
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_when_minute_matches(hass, calls):
    """Test for firing if minutes are matching."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "time_pattern",
                    "hours": "*",
                    "minutes": 0,
                    "seconds": "*",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_time_changed(hass, dt_util.utcnow().replace(minute=0))

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_when_second_matches(hass, calls):
    """Test for firing if seconds are matching."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "time_pattern",
                    "hours": "*",
                    "minutes": "*",
                    "seconds": 0,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_time_changed(hass, dt_util.utcnow().replace(second=0))

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_when_all_matches(hass, calls):
    """Test for firing if everything matches."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "time_pattern",
                    "hours": 1,
                    "minutes": 2,
                    "seconds": 3,
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_time_changed(hass, dt_util.utcnow().replace(hour=1, minute=2, second=3))

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_periodic_seconds(hass, calls):
    """Test for firing periodically every second."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "time_pattern",
                    "hours": "*",
                    "minutes": "*",
                    "seconds": "/2",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_time_changed(hass, dt_util.utcnow().replace(hour=0, minute=0, second=2))

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_periodic_minutes(hass, calls):
    """Test for firing periodically every minute."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "time_pattern",
                    "hours": "*",
                    "minutes": "/2",
                    "seconds": "*",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_time_changed(hass, dt_util.utcnow().replace(hour=0, minute=2, second=0))

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_if_fires_periodic_hours(hass, calls):
    """Test for firing periodically every hour."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "time_pattern",
                    "hours": "/2",
                    "minutes": "*",
                    "seconds": "*",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_time_changed(hass, dt_util.utcnow().replace(hour=2, minute=0, second=0))

    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_default_values(hass, calls):
    """Test for firing at 2 minutes every hour."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "time_pattern", "minutes": "2"},
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_time_changed(hass, dt_util.utcnow().replace(hour=1, minute=2, second=0))

    await hass.async_block_till_done()
    assert len(calls) == 1

    async_fire_time_changed(hass, dt_util.utcnow().replace(hour=1, minute=2, second=1))

    await hass.async_block_till_done()
    assert len(calls) == 1

    async_fire_time_changed(hass, dt_util.utcnow().replace(hour=2, minute=2, second=0))

    await hass.async_block_till_done()
    assert len(calls) == 2
