"""The tests for the time_pattern automation."""

from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant.components import automation
from homeassistant.components.homeassistant.triggers import time_pattern
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed, mock_component


@pytest.fixture(autouse=True)
def setup_comp(hass: HomeAssistant) -> None:
    """Initialize components."""
    mock_component(hass, "group")


@pytest.mark.parametrize(
    ("trigger_config", "event_time_kwargs"),
    [
        pytest.param(
            {"hours": 0, "minutes": "*", "seconds": "*"},
            {"hour": 0},
            id="test_if_fires_when_hour_matches",
        ),
        pytest.param(
            {"hours": "*", "minutes": 0, "seconds": "*"},
            {"minute": 0},
            id="test_if_fires_when_minute_matches",
        ),
        pytest.param(
            {"hours": "*", "minutes": "*", "seconds": 0},
            {"second": 0},
            id="test_if_fires_when_second_matches",
        ),
        pytest.param(
            {"hours": "*", "minutes": "*", "seconds": "30"},
            {"second": 30},
            id="test_if_fires_when_second_as_string_matches",
        ),
        pytest.param(
            {"hours": 1, "minutes": 2, "seconds": 3},
            {"hour": 1, "minute": 2, "second": 3},
            id="test_if_fires_when_all_matches",
        ),
        pytest.param(
            {"hours": "*", "minutes": "*", "seconds": "/10"},
            {"second": 10},
            id="test_if_fires_periodic_seconds",
        ),
        pytest.param(
            {"hours": "*", "minutes": "/2", "seconds": "*"},
            {"minute": 2, "second": 0},
            id="test_if_fires_periodic_minutes",
        ),
        pytest.param(
            {"hours": "/2", "minutes": "*", "seconds": "*"},
            {"hour": 2, "minute": 0, "second": 0},
            id="test_if_fires_periodic_hours",
        ),
        pytest.param(
            {"hours": "*", "minutes": "*", "seconds": "10-30"},
            {"second": 10},
            id="test_if_fires_range_seconds",
        ),
        pytest.param(
            {"hours": "*", "minutes": "20-40", "seconds": "*"},
            {"minute": 33},
            id="test_if_fires_range_seconds",
        ),
        pytest.param(
            {"hours": "3-5", "minutes": "*", "seconds": "*"},
            {"hour": 5},
            id="test_if_fires_range_seconds",
        ),
        pytest.param(
            {"hours": "*", "minutes": "*", "seconds": "5,3,10"},
            {"second": 3},
            id="test_if_fires_range_seconds",
        ),
        pytest.param(
            {"hours": "*", "minutes": "10,25", "seconds": "*"},
            {"minute": 10},
            id="test_if_fires_range_seconds",
        ),
        pytest.param(
            {"hours": "7,11,17", "minutes": "*", "seconds": "*"},
            {"hour": 17},
            id="test_if_fires_range_seconds",
        ),
        pytest.param(
            {"hours": "7-9,11-17", "minutes": "*", "seconds": "*"},
            {"hour": 14},
            id="test_if_fires_range_seconds",
        ),
        pytest.param(
            {"minutes": "2"},
            {"minute": 2, "second": 0},
            id="test_if_fires_range_seconds",
        ),
    ],
)
async def test_time_pattern_match(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
    trigger_config: dict[str, str | int],
    event_time_kwargs: dict[str, int],
) -> None:
    """Test standard time pattern matching."""
    now = dt_util.utcnow()
    # Move to a time that definitely won't match (1 year ahead, specific odd time)
    # ensuring we don't accidentally trigger on startup
    initial_safe_time = now.replace(
        year=now.year + 1, day=1, hour=23, minute=59, second=59
    )
    freezer.move_to(initial_safe_time)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "time_pattern",
                    **trigger_config,
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {"id": "{{ trigger.id}}"},
                },
            }
        },
    )

    match_time = now.replace(year=now.year + 2, day=1, **event_time_kwargs)
    async_fire_time_changed(hass, match_time)
    await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_automation_lifecycle(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
) -> None:
    """Test that the automation can be turned off (listener unsubscribed)."""
    now = dt_util.utcnow()
    freezer.move_to(now.replace(year=now.year + 1))

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

    async_fire_time_changed(hass, now.replace(year=now.year + 2, day=1, hour=0))
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )
    assert len(service_calls) == 2

    async_fire_time_changed(hass, now.replace(year=now.year + 3, day=1, hour=0))
    await hass.async_block_till_done()
    assert len(service_calls) == 2


@pytest.mark.parametrize(
    "config",
    [
        None,
        {},
        {"platform": "time_pattern"},
        {"platform": "time_pattern", "minutes": "/"},
        {"platform": "time_pattern", "minutes": "*/5"},
        {"platform": "time_pattern", "minutes": "/90"},
        {"platform": "time_pattern", "hours": "/0", "minutes": 10},
        {"platform": "time_pattern", "hours": 12, "minutes": 0, "seconds": 100},
    ],
)
async def test_invalid_schemas(config) -> None:
    """Test invalid schemas."""
    with pytest.raises(vol.Invalid):
        time_pattern.TRIGGER_SCHEMA(config)
