"""Test mobile app timers."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.mobile_app import DATA_DEVICES, DOMAIN
from homeassistant.components.timer_list import DOMAIN as TIMER_LIST_DOMAIN
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, intent as intent_helper
from homeassistant.setup import async_setup_component

TIMER_LIST_ENTITY_ID = "timer_list.test_1_timers"


@pytest.fixture(autouse=True)
async def setup_intent(hass: HomeAssistant) -> None:
    """Set up the intent integration that handles voice timers."""
    assert await async_setup_component(hass, "intent", {})


@pytest.fixture
def mock_send_message() -> Generator[AsyncMock]:
    """Mock sending a push notification."""
    with patch(
        "homeassistant.components.mobile_app.notify.MobileAppNotificationService.async_send_message"
    ) as mock_send_message:
        yield mock_send_message


@pytest.mark.parametrize(
    ("intent_args", "added_minutes", "message"),
    [
        pytest.param({}, 0, "0:02:00 timer finished", id="unnamed"),
        pytest.param({}, 1, "0:03:00 timer finished", id="unnamed_time_added"),
        pytest.param({"name": {"value": "pizza"}}, 0, "pizza finished", id="named"),
    ],
)
async def test_timer_events(
    hass: HomeAssistant,
    push_registration: dict[str, Any],
    mock_send_message: AsyncMock,
    intent_args: dict[str, Any],
    added_minutes: int,
    message: str,
) -> None:
    """Test a finished voice timer is sent as a push notification."""
    webhook_id = push_registration["webhook_id"]
    device_id = hass.data[DOMAIN][DATA_DEVICES][webhook_id].id

    await intent_helper.async_handle(
        hass,
        "test",
        intent_helper.INTENT_START_TIMER,
        {"minutes": {"value": 2}} | intent_args,
        device_id=device_id,
    )
    await intent_helper.async_handle(
        hass,
        "test",
        intent_helper.INTENT_INCREASE_TIMER,
        {"minutes": {"value": added_minutes}},
        device_id=device_id,
    )
    await hass.async_block_till_done()
    assert hass.states.get(TIMER_LIST_ENTITY_ID).state == "1"
    mock_send_message.assert_not_called()

    await intent_helper.async_handle(
        hass,
        "test",
        intent_helper.INTENT_DECREASE_TIMER,
        {"minutes": {"value": 2 + added_minutes}},
        device_id=device_id,
    )
    await hass.async_block_till_done()

    assert mock_send_message.mock_calls[0][2] == {
        "target": [webhook_id],
        "message": message,
        "data": {
            "channel": "Timers",
            "group": "timers",
            "importance": "high",
            "ttl": 0,
            "priority": "high",
            "push": {
                "interruption-level": "time-sensitive",
            },
        },
    }


@pytest.mark.usefixtures("push_registration")
async def test_cancelled_timer_is_not_sent(
    hass: HomeAssistant, mock_send_message: AsyncMock
) -> None:
    """Test only finished timers are sent as push notifications."""
    result = await hass.services.async_call(
        TIMER_LIST_DOMAIN,
        "create_timer",
        {"duration": {"minutes": 2}},
        target={TargetKey.ENTITY_ID: TIMER_LIST_ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    await hass.services.async_call(
        TIMER_LIST_DOMAIN,
        "cancel_timer",
        {"timer_id": result[TIMER_LIST_ENTITY_ID]["timer_id"]},
        target={TargetKey.ENTITY_ID: TIMER_LIST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_send_message.assert_not_called()


@pytest.mark.usefixtures("create_registrations")
async def test_no_timer_list_without_push(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a device that cannot receive push notifications has no timer list."""
    assert not [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == Platform.TIMER_LIST
    ]
