"""The tests for the time_pattern automation."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant.components import automation
from homeassistant.components.homeassistant.triggers import time_pattern
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, mock_component


@pytest.fixture(autouse=True)
def setup_comp(hass: HomeAssistant) -> None:
    """Initialize components."""
    mock_component(hass, "group")


async def test_if_fires_when_hour_matches(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
) -> None:
    """Test for firing if hour is matching."""
    now = dt_util.utcnow()
    time_that_will_not_match_right_away = dt_util.utcnow().replace(
        year=now.year + 1, day=1, hour=3
    )
    freezer.move_to(time_that_will_not_match_right_away)
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
                "action": {
                    "service": "test.automation",
                    "data_template": {"id": "{{ trigger.id}}"},
                },
            }
        },
    )

    async_fire_time_changed(hass, now.replace(year=now.year + 2, day=1, hour=0))
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["id"] == 0

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )
    assert len(service_calls) == 2

    async_fire_time_changed(hass, now.replace(year=now.year + 1, day=1, hour=0))
    await hass.async_block_till_done()
    assert len(service_calls) == 2


async def test_if_fires_when_minute_matches(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
) -> None:
    """Test for firing if minutes are matching."""
    now = dt_util.utcnow()
    time_that_will_not_match_right_away = dt_util.utcnow().replace(
        year=now.year + 1, day=1, minute=30
    )
    freezer.move_to(time_that_will_not_match_right_away)
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

    async_fire_time_changed(hass, now.replace(year=now.year + 2, day=1, minute=0))

    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_when_second_matches(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
) -> None:
    """Test for firing if seconds are matching."""
    now = dt_util.utcnow()
    time_that_will_not_match_right_away = dt_util.utcnow().replace(
        year=now.year + 1, day=1, second=30
    )
    freezer.move_to(time_that_will_not_match_right_away)
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

    async_fire_time_changed(hass, now.replace(year=now.year + 2, day=1, second=0))

    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_when_second_as_string_matches(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
) -> None:
    """Test for firing if seconds are matching."""
    now = dt_util.utcnow()
    time_that_will_not_match_right_away = dt_util.utcnow().replace(
        year=now.year + 1, day=1, second=15
    )
    freezer.move_to(time_that_will_not_match_right_away)
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "time_pattern",
                    "hours": "*",
                    "minutes": "*",
                    "seconds": "30",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_time_changed(
        hass, time_that_will_not_match_right_away + timedelta(seconds=15)
    )

    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_when_all_matches(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
) -> None:
    """Test for firing if everything matches."""
    now = dt_util.utcnow()
    time_that_will_not_match_right_away = dt_util.utcnow().replace(
        year=now.year + 1, day=1, hour=4
    )
    freezer.move_to(time_that_will_not_match_right_away)
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

    async_fire_time_changed(
        hass, now.replace(year=now.year + 2, day=1, hour=1, minute=2, second=3)
    )

    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_periodic_seconds(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
) -> None:
    """Test for firing periodically every second."""
    now = dt_util.utcnow()
    time_that_will_not_match_right_away = dt_util.utcnow().replace(
        year=now.year + 1, day=1, second=1
    )
    freezer.move_to(time_that_will_not_match_right_away)
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "time_pattern",
                    "hours": "*",
                    "minutes": "*",
                    "seconds": "/10",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    async_fire_time_changed(
        hass, now.replace(year=now.year + 2, day=1, hour=0, minute=0, second=10)
    )

    await hass.async_block_till_done()
    assert len(service_calls) >= 1


async def test_if_fires_periodic_minutes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
) -> None:
    """Test for firing periodically every minute."""

    now = dt_util.utcnow()
    time_that_will_not_match_right_away = dt_util.utcnow().replace(
        year=now.year + 1, day=1, minute=1
    )
    freezer.move_to(time_that_will_not_match_right_away)
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

    async_fire_time_changed(
        hass, now.replace(year=now.year + 2, day=1, hour=0, minute=2, second=0)
    )

    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_periodic_hours(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
) -> None:
    """Test for firing periodically every hour."""
    now = dt_util.utcnow()
    time_that_will_not_match_right_away = dt_util.utcnow().replace(
        year=now.year + 1, day=1, hour=1
    )
    freezer.move_to(time_that_will_not_match_right_away)
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

    async_fire_time_changed(
        hass, now.replace(year=now.year + 2, day=1, hour=2, minute=0, second=0)
    )

    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_default_values(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
) -> None:
    """Test for firing at 2 minutes every hour."""
    now = dt_util.utcnow()
    time_that_will_not_match_right_away = dt_util.utcnow().replace(
        year=now.year + 1, day=1, minute=1
    )
    freezer.move_to(time_that_will_not_match_right_away)
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

    async_fire_time_changed(
        hass, now.replace(year=now.year + 2, day=1, hour=1, minute=2, second=0)
    )

    await hass.async_block_till_done()
    assert len(service_calls) == 1

    async_fire_time_changed(
        hass, now.replace(year=now.year + 2, day=1, hour=1, minute=2, second=1)
    )

    await hass.async_block_till_done()
    assert len(service_calls) == 1

    async_fire_time_changed(
        hass, now.replace(year=now.year + 2, day=1, hour=2, minute=2, second=0)
    )

    await hass.async_block_till_done()
    assert len(service_calls) == 2


async def test_invalid_schemas() -> None:
    """Test invalid schemas."""
    schemas = (
        None,
        {},
        {"platform": "time_pattern"},
        {"platform": "time_pattern", "minutes": "/"},
        {"platform": "time_pattern", "minutes": "*/5"},
        {"platform": "time_pattern", "minutes": "/90"},
        {"platform": "time_pattern", "hours": 12, "minutes": 0, "seconds": 100},
    )

    for value in schemas:
        with pytest.raises(vol.Invalid):
            time_pattern.TRIGGER_SCHEMA(value)
