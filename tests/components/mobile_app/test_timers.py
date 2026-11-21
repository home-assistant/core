"""Test mobile app timers."""

from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, patch

from aiohttp.test_utils import TestClient
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.intent import TIMER_DATA
from homeassistant.components.mobile_app import DATA_DEVICES, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent as intent_helper
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .const import REGISTER

SEND_MESSAGE = (
    "homeassistant.components.mobile_app.notify.MobileAppNotificationService"
    ".async_send_message"
)

FINISHED_DATA = {
    "channel": "Timers",
    "group": "timers",
    "importance": "high",
    "ttl": 0,
    "priority": "high",
    "push": {
        "interruption-level": "time-sensitive",
    },
}


async def _async_register(
    hass: HomeAssistant, webhook_client: TestClient, app_data: dict[str, Any]
) -> dict[str, Any]:
    """Register a push capable device with extra app data."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    reg = await webhook_client.post(
        "/api/mobile_app/registrations",
        json={
            **REGISTER,
            "app_data": {
                "push_url": "http://localhost/mock-push",
                "push_token": "abcd",
                **app_data,
            },
        },
    )

    assert reg.status == HTTPStatus.CREATED
    return await reg.json()


@pytest.fixture
async def live_activity_registration(
    hass: HomeAssistant, webhook_client: TestClient
) -> dict[str, Any]:
    """Return a registration that can start Live Activities."""
    return await _async_register(
        hass,
        webhook_client,
        {"start_live_activity_token": "PUSH_TO_START_HEX_TOKEN"},
    )


async def _async_handle_timer_intent(
    hass: HomeAssistant, intent_type: str, device_id: str, slots: dict[str, Any]
) -> None:
    await intent_helper.async_handle(
        hass, "test", intent_type, slots, device_id=device_id
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "app_data",
    [
        pytest.param({}, id="no_start_live_activity_token"),
        pytest.param(
            {"start_live_activity_token": ""}, id="empty_start_live_activity_token"
        ),
    ],
)
@pytest.mark.parametrize(
    ("intent_args", "message"),
    [
        (
            {},
            "0:02:00 timer finished",
        ),
        (
            {"name": {"value": "pizza"}},
            "pizza finished",
        ),
    ],
)
async def test_timer_events(
    hass: HomeAssistant,
    webhook_client: TestClient,
    app_data: dict[str, Any],
    intent_args: dict,
    message: str,
) -> None:
    """Test for timer events."""
    registration = await _async_register(hass, webhook_client, app_data)
    webhook_id = registration["webhook_id"]
    device_id = hass.data[DOMAIN][DATA_DEVICES][webhook_id].id

    with patch(SEND_MESSAGE) as mock_send_message:
        await _async_handle_timer_intent(
            hass,
            intent_helper.INTENT_START_TIMER,
            device_id,
            {"minutes": {"value": 2}} | intent_args,
        )
        await _async_handle_timer_intent(
            hass,
            intent_helper.INTENT_DECREASE_TIMER,
            device_id,
            {"minutes": {"value": 2}},
        )

    # Devices without Live Activity support only hear about the timer finishing.
    assert mock_send_message.mock_calls == [
        (
            "",
            (),
            {
                "target": [webhook_id],
                "message": message,
                "data": FINISHED_DATA,
            },
        )
    ]


def _sent(mock_send_message: MagicMock) -> list[dict[str, Any]]:
    """Return the keyword arguments of each notification sent."""
    return [call.kwargs for call in mock_send_message.mock_calls]


def _timer_tag(hass: HomeAssistant) -> str:
    """Return the Live Activity tag of the only running timer."""
    (timer_id,) = hass.data[TIMER_DATA].timers
    return f"timer-{timer_id}"


async def test_timer_live_activity(
    hass: HomeAssistant,
    live_activity_registration: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a timer is mirrored in a Live Activity until it is cancelled."""
    webhook_id = live_activity_registration["webhook_id"]
    device_id = hass.data[DOMAIN][DATA_DEVICES][webhook_id].id
    now = dt_util.utcnow().timestamp()

    with patch(SEND_MESSAGE) as mock_send_message:
        await _async_handle_timer_intent(
            hass,
            intent_helper.INTENT_START_TIMER,
            device_id,
            {"minutes": {"value": 2}, "name": {"value": "pizza"}},
        )
        tag = _timer_tag(hass)
        assert _sent(mock_send_message) == [
            {
                "target": [webhook_id],
                "title": "pizza",
                "message": "0:02:00",
                "data": {
                    "tag": tag,
                    "live_update": True,
                    "notification_icon": "mdi:timer-outline",
                    "chronometer": True,
                    "when": now + 120,
                    "when_relative": False,
                    "alert": {"title": "pizza", "body": "0:02:00"},
                    "alert_sound": "default",
                },
            }
        ]
        mock_send_message.reset_mock()

        freezer.tick(30)
        await _async_handle_timer_intent(
            hass, intent_helper.INTENT_PAUSE_TIMER, device_id, {}
        )
        assert _sent(mock_send_message) == [
            {
                "target": [webhook_id],
                "title": "pizza",
                "message": "0:01:30 left",
                "data": {
                    "tag": tag,
                    "live_update": True,
                    "silent": True,
                    "notification_icon": "mdi:timer-outline",
                    "chronometer": False,
                    "critical_text": "Paused",
                    "progress": 90,
                    "progress_max": 120,
                },
            }
        ]
        mock_send_message.reset_mock()

        freezer.tick(60)
        await _async_handle_timer_intent(
            hass, intent_helper.INTENT_UNPAUSE_TIMER, device_id, {}
        )
        assert _sent(mock_send_message) == [
            {
                "target": [webhook_id],
                "title": "pizza",
                "message": "0:02:00",
                "data": {
                    "tag": tag,
                    "live_update": True,
                    "silent": True,
                    "notification_icon": "mdi:timer-outline",
                    "chronometer": True,
                    "when": now + 90 + 90,
                    "when_relative": False,
                },
            }
        ]

        mock_send_message.reset_mock()
        await _async_handle_timer_intent(
            hass,
            intent_helper.INTENT_INCREASE_TIMER,
            device_id,
            {"minutes": {"value": 1}},
        )
        # Adding time past the original duration also raises the created duration.
        assert _sent(mock_send_message) == [
            {
                "target": [webhook_id],
                "title": "pizza",
                "message": "0:02:30",
                "data": {
                    "tag": tag,
                    "live_update": True,
                    "silent": True,
                    "notification_icon": "mdi:timer-outline",
                    "chronometer": True,
                    "when": now + 90 + 150,
                    "when_relative": False,
                },
            }
        ]

        mock_send_message.reset_mock()
        await _async_handle_timer_intent(
            hass, intent_helper.INTENT_CANCEL_TIMER, device_id, {}
        )
        assert _sent(mock_send_message) == [
            {
                "target": [webhook_id],
                "message": "clear_notification",
                "data": {"tag": tag},
            }
        ]


async def test_timer_live_activity_finished(
    hass: HomeAssistant, live_activity_registration: dict[str, Any]
) -> None:
    """Test a finished timer shows an alerting end state in its Live Activity."""
    webhook_id = live_activity_registration["webhook_id"]
    device_id = hass.data[DOMAIN][DATA_DEVICES][webhook_id].id

    with patch(SEND_MESSAGE) as mock_send_message:
        await _async_handle_timer_intent(
            hass,
            intent_helper.INTENT_START_TIMER,
            device_id,
            {"minutes": {"value": 2}},
        )
        tag = _timer_tag(hass)
        mock_send_message.reset_mock()

        await _async_handle_timer_intent(
            hass,
            intent_helper.INTENT_DECREASE_TIMER,
            device_id,
            {"minutes": {"value": 2}},
        )

    # No separate finished notification: the end state replaces it.
    assert _sent(mock_send_message) == [
        {
            "target": [webhook_id],
            "title": "Timer",
            "message": "Finished",
            "data": {
                "tag": tag,
                "live_update": True,
                "notification_icon": "mdi:timer-outline",
                "chronometer": False,
                "alert": {"title": "Timer", "body": "Finished"},
                "alert_sound": "default",
            },
        },
    ]
