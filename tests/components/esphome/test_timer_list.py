"""Test ESPHome timer lists."""

from datetime import timedelta
from typing import Any
from unittest.mock import ANY, call

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    VoiceAssistantFeature,
    VoiceAssistantTimerEventType,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from homeassistant.components.esphome.const import DOMAIN
from homeassistant.components.timer_list import DOMAIN as TIMER_LIST_DOMAIN
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er, intent

from .common import get_satellite_entity
from .conftest import (
    MockESPHomeDevice,
    MockESPHomeDeviceType,
    reconnect_with_updated_entity_info,
)

TIMER_FLAGS = VoiceAssistantFeature.VOICE_ASSISTANT | VoiceAssistantFeature.TIMERS
STARTED = VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_STARTED
UPDATED = VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_UPDATED
CANCELLED = VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_CANCELLED
FINISHED = VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_FINISHED


@pytest.fixture
async def mock_device(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> MockESPHomeDevice:
    """Set up an ESPHome voice satellite that supports timers."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"voice_assistant_feature_flags": TIMER_FLAGS},
    )
    await hass.async_block_till_done()
    return device


def _timer_list_entity_id(hass: HomeAssistant, device: MockESPHomeDevice) -> str | None:
    """Return the entity id of the device's timer list."""
    return er.async_get(hass).async_get_entity_id(
        Platform.TIMER_LIST, DOMAIN, f"{device.device_info.mac_address}-timer_list"
    )


def _device_id(hass: HomeAssistant, device: MockESPHomeDevice) -> str:
    """Return the device registry id of the ESPHome device."""
    assert device.entry.unique_id is not None
    device_entry = dr.async_get(hass).async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, device.entry.unique_id), device.entry.entry_id
    )
    assert device_entry is not None
    return device_entry.id


async def _handle(
    hass: HomeAssistant, device: MockESPHomeDevice, intent_type: str, **slots: Any
) -> None:
    """Handle a timer intent spoken on the device."""
    await intent.async_handle(
        hass,
        "test",
        intent_type,
        {name: {"value": value} for name, value in slots.items()},
        device_id=_device_id(hass, device),
    )


async def _call(hass: HomeAssistant, entity_id: str, service: str, **data: Any) -> Any:
    """Call a timer list action."""
    result = await hass.services.async_call(
        TIMER_LIST_DOMAIN,
        service,
        data,
        target={TargetKey.ENTITY_ID: entity_id},
        blocking=True,
        return_response=service == "create_timer",
    )
    return result[entity_id] if result else None


@pytest.mark.usefixtures("freezer")
async def test_voice_timer_events(
    hass: HomeAssistant, mock_client: APIClient, mock_device: MockESPHomeDevice
) -> None:
    """Test changes to a voice timer are sent to the device."""
    entity_id = _timer_list_entity_id(hass, mock_device)
    assert entity_id == "timer_list.test_timers"

    await _handle(
        hass,
        mock_device,
        intent.INTENT_START_TIMER,
        name="test timer",
        hours=1,
        minutes=2,
        seconds=3,
    )
    await _handle(hass, mock_device, intent.INTENT_INCREASE_TIMER, minutes=5)
    await _handle(hass, mock_device, intent.INTENT_PAUSE_TIMER)
    await _handle(hass, mock_device, intent.INTENT_UNPAUSE_TIMER)
    await _handle(hass, mock_device, intent.INTENT_DECREASE_TIMER, minutes=10)
    await _handle(hass, mock_device, intent.INTENT_CANCEL_TIMER)

    assert hass.states.get(entity_id).state == "0"
    assert mock_client.send_voice_assistant_timer_event.mock_calls == [
        call(STARTED, ANY, "test timer", 3723, 3723, True),
        # Added time raises the total
        call(UPDATED, ANY, "test timer", 4023, 4023, True),
        call(UPDATED, ANY, "test timer", 4023, 4023, False),
        call(UPDATED, ANY, "test timer", 4023, 4023, True),
        # Removed time does not lower it
        call(UPDATED, ANY, "test timer", 4023, 3423, True),
        call(CANCELLED, ANY, "test timer", 4023, 0, False),
    ]
    timer_ids = {
        event.args[1]
        for event in mock_client.send_voice_assistant_timer_event.mock_calls
    }
    assert len(timer_ids) == 1


@pytest.mark.usefixtures("freezer")
@pytest.mark.parametrize(
    ("duration_seconds", "expected_seconds"), [(0.4, 1), (10.2, 11)]
)
async def test_fractional_duration_timer_event(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_device: MockESPHomeDevice,
    duration_seconds: float,
    expected_seconds: int,
) -> None:
    """Round fractional durations up consistently in device timer events."""
    entity_id = _timer_list_entity_id(hass, mock_device)
    assert entity_id is not None

    result = await _call(
        hass, entity_id, "create_timer", duration={"seconds": duration_seconds}
    )

    mock_client.send_voice_assistant_timer_event.assert_called_once_with(
        STARTED, result["timer_id"], None, expected_seconds, expected_seconds, True
    )


async def test_pause_unpause_fractional_second(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: APIClient,
    mock_device: MockESPHomeDevice,
) -> None:
    """Keep positive remaining time visible when pausing and resuming a timer."""
    entity_id = _timer_list_entity_id(hass, mock_device)
    assert entity_id is not None
    result = await _call(hass, entity_id, "create_timer", duration={"seconds": 1})
    timer_id = result["timer_id"]
    mock_client.send_voice_assistant_timer_event.reset_mock()

    freezer.tick(timedelta(milliseconds=600))
    await _call(hass, entity_id, "pause_timer", timer_id=timer_id)
    freezer.tick(timedelta(seconds=1))
    await _call(hass, entity_id, "unpause_timer", timer_id=timer_id)

    assert mock_client.send_voice_assistant_timer_event.mock_calls == [
        call(UPDATED, timer_id, None, 1, 1, False),
        call(UPDATED, timer_id, None, 1, 1, True),
    ]


async def test_timer_finished(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: APIClient,
    mock_device: MockESPHomeDevice,
) -> None:
    """Test the device is told when a timer finishes, so it rings."""
    entity_id = _timer_list_entity_id(hass, mock_device)
    assert entity_id is not None
    result = await _call(hass, entity_id, "create_timer", duration={"seconds": 60})
    mock_client.send_voice_assistant_timer_event.reset_mock()

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_client.send_voice_assistant_timer_event.assert_called_once_with(
        FINISHED, result["timer_id"], None, 60, 0, False
    )


@pytest.mark.usefixtures("freezer")
@pytest.mark.parametrize(
    ("setup_services", "expected_calls"),
    [
        pytest.param([], [call(CANCELLED, ANY, None, 60, 0, False)], id="active"),
        pytest.param(
            ["pause_timer"], [call(CANCELLED, ANY, None, 60, 0, False)], id="paused"
        ),
        pytest.param(["cancel_timer"], [], id="cancelled"),
        pytest.param(["finish_timer"], [], id="finished"),
    ],
)
async def test_remove_timer(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_device: MockESPHomeDevice,
    setup_services: list[str],
    expected_calls: list[Any],
) -> None:
    """Test removing a timer the device still shows cancels it there."""
    entity_id = _timer_list_entity_id(hass, mock_device)
    assert entity_id is not None
    result = await _call(hass, entity_id, "create_timer", duration={"seconds": 60})
    for service in setup_services:
        await _call(hass, entity_id, service, timer_id=result["timer_id"])
    mock_client.send_voice_assistant_timer_event.reset_mock()

    await _call(hass, entity_id, "remove_timer", timer_id=result["timer_id"])

    assert mock_client.send_voice_assistant_timer_event.mock_calls == expected_calls


@pytest.mark.usefixtures("freezer")
async def test_timers_kept_while_disconnected(
    hass: HomeAssistant, mock_client: APIClient, mock_device: MockESPHomeDevice
) -> None:
    """Test timers keep running while the device is disconnected."""
    entity_id = _timer_list_entity_id(hass, mock_device)
    assert entity_id is not None
    result = await _call(hass, entity_id, "create_timer", duration={"seconds": 60})
    mock_client.send_voice_assistant_timer_event.reset_mock()

    await mock_device.mock_disconnect(expected_disconnect=False)
    await hass.async_block_till_done()
    await _call(
        hass,
        entity_id,
        "add_time",
        timer_id=result["timer_id"],
        duration={"seconds": 30},
    )

    mock_client.send_voice_assistant_timer_event.assert_not_called()
    assert hass.states.get(entity_id).state == "1"

    await mock_device.mock_connect()
    await hass.async_block_till_done()
    await _call(hass, entity_id, "pause_timer", timer_id=result["timer_id"])

    assert hass.states.get(entity_id).state == "0"
    assert mock_client.send_voice_assistant_timer_event.mock_calls == [
        # The change missed while disconnected
        call(UPDATED, result["timer_id"], None, 90, 90, True),
        call(UPDATED, result["timer_id"], None, 90, 90, False),
    ]


async def test_timers_resent_on_reconnect(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: APIClient,
    mock_device: MockESPHomeDevice,
) -> None:
    """Test the device gets its running timers again when it reconnects."""
    entity_id = _timer_list_entity_id(hass, mock_device)
    assert entity_id is not None
    cancelled = await _call(
        hass, entity_id, "create_timer", name="cancelled", duration={"seconds": 60}
    )
    finished = await _call(
        hass, entity_id, "create_timer", name="finished", duration={"seconds": 60}
    )
    ran_out = await _call(
        hass, entity_id, "create_timer", name="ran out", duration={"seconds": 20}
    )
    removed = await _call(
        hass, entity_id, "create_timer", name="removed", duration={"seconds": 60}
    )
    paused = await _call(
        hass, entity_id, "create_timer", name="paused", duration={"seconds": 120}
    )
    kept = await _call(
        hass, entity_id, "create_timer", name="kept", duration={"seconds": 300}
    )

    await mock_device.mock_disconnect(expected_disconnect=False)
    await hass.async_block_till_done()
    await _call(hass, entity_id, "cancel_timer", timer_id=cancelled["timer_id"])
    await _call(hass, entity_id, "finish_timer", timer_id=finished["timer_id"])
    await _call(hass, entity_id, "remove_timer", timer_id=removed["timer_id"])
    await _call(hass, entity_id, "pause_timer", timer_id=paused["timer_id"])
    new = await _call(
        hass, entity_id, "create_timer", name="new", duration={"seconds": 30}
    )
    freezer.tick(timedelta(seconds=25))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_client.send_voice_assistant_timer_event.reset_mock()

    await mock_device.mock_connect()
    await hass.async_block_till_done()

    assert mock_client.send_voice_assistant_timer_event.mock_calls == [
        # Ended while disconnected: cancelled, so the device does not ring late
        call(CANCELLED, cancelled["timer_id"], "cancelled", 0, 0, False),
        call(CANCELLED, finished["timer_id"], "finished", 0, 0, False),
        call(CANCELLED, ran_out["timer_id"], "ran out", 0, 0, False),
        call(CANCELLED, removed["timer_id"], "removed", 0, 0, False),
        call(UPDATED, paused["timer_id"], "paused", 120, 120, False),
        call(UPDATED, kept["timer_id"], "kept", 300, 275, True),
        call(UPDATED, new["timer_id"], "new", 30, 5, True),
    ]

    # Only what changed is sent on the next reconnect
    await mock_device.mock_disconnect(expected_disconnect=False)
    await hass.async_block_till_done()
    mock_client.send_voice_assistant_timer_event.reset_mock()
    await mock_device.mock_connect()
    await hass.async_block_till_done()

    assert mock_client.send_voice_assistant_timer_event.mock_calls == [
        call(UPDATED, paused["timer_id"], "paused", 120, 120, False),
        call(UPDATED, kept["timer_id"], "kept", 300, 275, True),
        call(UPDATED, new["timer_id"], "new", 30, 5, True),
    ]


@pytest.mark.usefixtures("freezer")
async def test_cancel_retried_after_failed_send(
    hass: HomeAssistant, mock_client: APIClient, mock_device: MockESPHomeDevice
) -> None:
    """Test a cancellation that could not be sent is sent on the next reconnect."""
    entity_id = _timer_list_entity_id(hass, mock_device)
    assert entity_id is not None
    result = await _call(hass, entity_id, "create_timer", duration={"seconds": 60})
    timer_id = result["timer_id"]
    await mock_device.mock_disconnect(expected_disconnect=False)
    await hass.async_block_till_done()
    await _call(hass, entity_id, "cancel_timer", timer_id=timer_id)

    # The connection drops again while the cancellation is being sent
    mock_client.send_voice_assistant_timer_event.reset_mock()
    mock_client.send_voice_assistant_timer_event.side_effect = APIConnectionError(
        "Connection lost"
    )
    await mock_device.mock_connect()
    await hass.async_block_till_done()
    await mock_device.mock_disconnect(expected_disconnect=False)
    await hass.async_block_till_done()

    mock_client.send_voice_assistant_timer_event.side_effect = None
    mock_client.send_voice_assistant_timer_event.reset_mock()
    await mock_device.mock_connect()
    await hass.async_block_till_done()

    mock_client.send_voice_assistant_timer_event.assert_called_once_with(
        CANCELLED, timer_id, None, 0, 0, False
    )


@pytest.mark.usefixtures("freezer")
async def test_resent_after_the_satellite_subscribes(
    hass: HomeAssistant, mock_client: APIClient, mock_device: MockESPHomeDevice
) -> None:
    """Test timers are resent only once the satellite is subscribed again.

    The firmware drops timer events from a connection that is not subscribed to
    its voice assistant, and the satellite subscribes after the device is
    available again.
    """
    entity_id = _timer_list_entity_id(hass, mock_device)
    assert entity_id is not None
    result = await _call(hass, entity_id, "create_timer", duration={"seconds": 60})
    await mock_device.mock_disconnect(expected_disconnect=False)
    await hass.async_block_till_done()
    mock_client.send_voice_assistant_timer_event.reset_mock()

    order: list[str] = []
    subscribe = mock_client.subscribe_voice_assistant

    def _subscribe(**kwargs: Any) -> Any:
        order.append("subscribe")
        return subscribe(**kwargs)

    mock_client.subscribe_voice_assistant = _subscribe
    mock_client.send_voice_assistant_timer_event.side_effect = lambda *args: (
        order.append("send")
    )

    await mock_device.mock_connect()
    await hass.async_block_till_done()

    assert order == ["subscribe", "send"]
    mock_client.send_voice_assistant_timer_event.assert_called_once_with(
        UPDATED, result["timer_id"], None, 60, 60, True
    )


@pytest.mark.usefixtures("freezer")
async def test_nothing_sent_while_not_subscribed(
    hass: HomeAssistant, mock_client: APIClient, mock_device: MockESPHomeDevice
) -> None:
    """Test changes are kept for the next subscription while not subscribed."""
    entity_id = _timer_list_entity_id(hass, mock_device)
    assert entity_id is not None
    entry_data = mock_device.entry.runtime_data
    entry_data.async_set_voice_assistant_subscribed(False)

    result = await _call(hass, entity_id, "create_timer", duration={"seconds": 60})
    mock_client.send_voice_assistant_timer_event.assert_not_called()

    entry_data.async_set_voice_assistant_subscribed(True)
    mock_client.send_voice_assistant_timer_event.assert_called_once_with(
        UPDATED, result["timer_id"], None, 60, 60, True
    )


async def test_nothing_resent_without_timers(
    hass: HomeAssistant, mock_client: APIClient, mock_device: MockESPHomeDevice
) -> None:
    """Test a reconnect sends nothing when there are no timers."""
    await mock_device.mock_disconnect(expected_disconnect=False)
    await hass.async_block_till_done()
    await mock_device.mock_connect()
    await hass.async_block_till_done()

    mock_client.send_voice_assistant_timer_event.assert_not_called()


async def test_no_timer_list_without_timers(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a voice satellite without timers has no timer list."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
        },
    )
    await hass.async_block_till_done()

    assert _timer_list_entity_id(hass, device) is None
    assert Platform.TIMER_LIST not in device.entry.runtime_data.loaded_platforms
    satellite = get_satellite_entity(hass, device.device_info.mac_address)
    assert satellite is not None
    assert satellite.timer_list_entity_id is None


async def test_satellite_timer_list_entity_id(
    hass: HomeAssistant, mock_device: MockESPHomeDevice
) -> None:
    """Test the satellite names its device's timer list."""
    satellite = get_satellite_entity(hass, mock_device.device_info.mac_address)
    assert satellite is not None

    assert satellite.timer_list_entity_id == "timer_list.test_timers"


@pytest.mark.parametrize(
    "flags",
    [
        pytest.param(VoiceAssistantFeature.VOICE_ASSISTANT, id="timers_gone"),
        pytest.param(0, id="voice_assistant_gone"),
    ],
)
async def test_timer_list_follows_timers_feature(
    hass: HomeAssistant, mock_device: MockESPHomeDevice, flags: int
) -> None:
    """Test the timer list goes and comes back with the timers feature."""
    assert _timer_list_entity_id(hass, mock_device) is not None

    await reconnect_with_updated_entity_info(
        hass, mock_device, [], device_info={"voice_assistant_feature_flags": flags}
    )

    assert _timer_list_entity_id(hass, mock_device) is None
    assert Platform.TIMER_LIST not in mock_device.entry.runtime_data.loaded_platforms

    await reconnect_with_updated_entity_info(
        hass,
        mock_device,
        [],
        device_info={"voice_assistant_feature_flags": TIMER_FLAGS},
    )

    entity_id = _timer_list_entity_id(hass, mock_device)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "0"


@pytest.mark.freeze_time("2026-11-25T12:00:00+00:00")
async def test_timers_restored_after_restart(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test timers survive a restart and the device is brought up to date."""

    def stored(timer_id: str, status: str, **fields: Any) -> dict[str, Any]:
        return {
            "timer_id": timer_id,
            "name": timer_id,
            "status": status,
            "created_duration": 900.0,
            "created_at": "2026-11-25T11:50:00+00:00",
            "total_duration": 900.0,
            "finishes_at": None,
            "paused_remaining": None,
            "ended_at": None,
        } | fields

    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State("timer_list.test_timers", "2"),
                {
                    "timers": [
                        stored(
                            "running", "active", finishes_at="2026-11-25T12:05:00+00:00"
                        ),
                        stored("paused", "paused", paused_remaining=120.0),
                        stored(
                            "overdue", "active", finishes_at="2026-11-25T11:58:00+00:00"
                        ),
                        stored(
                            "archived",
                            "cancelled",
                            ended_at="2026-11-25T11:55:00+00:00",
                        ),
                    ]
                },
            )
        ],
    )

    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"voice_assistant_feature_flags": TIMER_FLAGS},
    )
    await hass.async_block_till_done()

    assert _timer_list_entity_id(hass, device) == "timer_list.test_timers"
    assert hass.states.get("timer_list.test_timers").state == "1"
    assert mock_client.send_voice_assistant_timer_event.mock_calls == [
        # Ran out while Home Assistant was stopped: dropped without ringing
        call(CANCELLED, "overdue", "overdue", 0, 0, False),
        call(UPDATED, "running", "running", 900, 300, True),
        call(UPDATED, "paused", "paused", 900, 120, False),
    ]


@pytest.mark.usefixtures("freezer")
async def test_timers_kept_on_reload(
    hass: HomeAssistant, mock_client: APIClient, mock_device: MockESPHomeDevice
) -> None:
    """Test reloading the integration keeps the timers."""
    entity_id = _timer_list_entity_id(hass, mock_device)
    assert entity_id is not None
    result = await _call(hass, entity_id, "create_timer", duration={"seconds": 60})
    mock_client.send_voice_assistant_timer_event.reset_mock()

    assert await hass.config_entries.async_reload(mock_device.entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "1"
    mock_client.send_voice_assistant_timer_event.assert_called_once_with(
        UPDATED, result["timer_id"], None, 60, 60, True
    )
