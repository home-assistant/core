"""Tests for the Timer list triggers."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import automation
from homeassistant.components.timer_list.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TARGET,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from . import MockTimerListEntity, create_mock_platform

from tests.common import async_fire_time_changed, async_mock_service
from tests.components.common import assert_trigger_options_supported

TEST_ENTITY_ID = "timer_list.timers"


@pytest.fixture
def service_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
async def setup_entity(hass: HomeAssistant) -> None:
    """Create a timer list entity via the mock platform."""
    entity = MockTimerListEntity()
    entity.entity_id = TEST_ENTITY_ID
    entity._attr_unique_id = "timers"
    await create_mock_platform(hass, [entity])


async def _setup_automation(
    hass: HomeAssistant, trigger_type: str, extra_data: dict[str, str] | None = None
) -> None:
    """Set up an automation for the given timer list trigger."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": [
                    {
                        CONF_PLATFORM: f"{DOMAIN}.{trigger_type}",
                        CONF_TARGET: {CONF_ENTITY_ID: TEST_ENTITY_ID},
                    }
                ],
                "action": {
                    "service": "test.automation",
                    "data": {
                        "entity_id": "{{ trigger.entity_id }}",
                        "timer_id": "{{ trigger.timer.timer_id }}",
                        "status": "{{ trigger.timer.status }}",
                        **(extra_data or {}),
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()


async def _create_timer(hass: HomeAssistant) -> str:
    """Create a timer and return its id."""
    result = await hass.services.async_call(
        DOMAIN,
        "create_timer",
        {"duration": {"seconds": 60}},
        target={ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    return result[TEST_ENTITY_ID]["timer_id"]


async def test_timer_finished_trigger(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the timer_finished trigger fires when a timer finishes."""
    await _setup_automation(hass, "timer_finished")
    timer_id = await _create_timer(hass)

    assert len(service_calls) == 0

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data == {
        "entity_id": TEST_ENTITY_ID,
        "timer_id": timer_id,
        "status": "finished",
    }


async def test_timer_created_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the timer_created trigger fires when a timer is created."""
    await _setup_automation(hass, "timer_created")
    timer_id = await _create_timer(hass)
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["timer_id"] == timer_id
    assert service_calls[0].data["status"] == "active"


async def test_timer_cancelled_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the timer_cancelled trigger fires and ignores other events."""
    await _setup_automation(hass, "timer_cancelled")
    timer_id = await _create_timer(hass)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    await hass.services.async_call(
        DOMAIN,
        "cancel_timer",
        {"timer_id": timer_id},
        target={ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    assert len(service_calls) == 1
    assert service_calls[0].data["status"] == "cancelled"


@pytest.mark.parametrize(
    ("trigger_type", "service", "expected_status"),
    [
        pytest.param("timer_paused", "pause_timer", "paused", id="paused"),
        pytest.param("timer_unpaused", "unpause_timer", "active", id="unpaused"),
    ],
)
async def test_pause_triggers(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_type: str,
    service: str,
    expected_status: str,
) -> None:
    """Test pausing and unpausing fire their own distinct triggers."""
    await _setup_automation(hass, trigger_type)
    timer_id = await _create_timer(hass)
    # Always pause first, so the unpause case has something to resume.
    await hass.services.async_call(
        DOMAIN,
        "pause_timer",
        {"timer_id": timer_id},
        target={ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        service,
        {"timer_id": timer_id},
        target={ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    assert len(service_calls) == 1
    assert service_calls[0].data["timer_id"] == timer_id
    assert service_calls[0].data["status"] == expected_status


@pytest.mark.parametrize(
    ("service", "expected_delta"),
    [
        pytest.param("add_time", 30.0, id="add_time"),
        pytest.param("subtract_time", -30.0, id="subtract_time"),
    ],
)
async def test_timer_time_changed_trigger_reports_delta(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    service: str,
    expected_delta: float,
) -> None:
    """Test the time_changed trigger reports the signed amount of time added."""
    await _setup_automation(
        hass, "timer_time_changed", extra_data={"delta": "{{ trigger.delta }}"}
    )
    timer_id = await _create_timer(hass)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    await hass.services.async_call(
        DOMAIN,
        service,
        {"timer_id": timer_id, "duration": {"seconds": 30}},
        target={ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    assert len(service_calls) == 1
    assert service_calls[0].data["timer_id"] == timer_id
    assert service_calls[0].data["delta"] == expected_delta


async def test_trigger_options_supported(hass: HomeAssistant) -> None:
    """Test the timer list triggers do not advertise behavior or duration."""
    for trigger_type in (
        "timer_created",
        "timer_paused",
        "timer_unpaused",
        "timer_time_changed",
        "timer_finished",
        "timer_cancelled",
    ):
        await assert_trigger_options_supported(
            hass,
            f"{DOMAIN}.{trigger_type}",
            None,
            supports_behavior=False,
            supports_duration=False,
        )
