"""Tests for the Timer list integration."""

from typing import Any

import pytest

from homeassistant.components.timer_list import async_get_timer_list_entity
from homeassistant.components.timer_list.const import DOMAIN, TimerListEntityFeature
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import TEST_DOMAIN, MockTimerListEntity, create_mock_platform

from tests.common import MockUser
from tests.typing import WebSocketGenerator

TEST_ENTITY_ID = "timer_list.timers"


async def _create_timer(
    hass: HomeAssistant,
    *,
    duration: int = 60,
    name: str | None = None,
) -> str:
    """Create a timer and return its id."""
    data: dict[str, Any] = {"duration": {"seconds": duration}}
    if name is not None:
        data[ATTR_NAME] = name
    result = await hass.services.async_call(
        DOMAIN,
        "create_timer",
        data,
        target={ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    return result[TEST_ENTITY_ID]["timer_id"]


async def _get_timers(
    hass: HomeAssistant, status: str | list[str] | None = None
) -> list[dict[str, Any]]:
    """Return the timers via the get_timers service."""
    data: dict[str, Any] = {}
    if status is not None:
        data["status"] = status
    result = await hass.services.async_call(
        DOMAIN,
        "get_timers",
        data,
        target={ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    return result[TEST_ENTITY_ID]["timers"]


async def _call(hass: HomeAssistant, service: str, **fields: Any) -> None:
    """Call an entity service targeting the test entity."""
    await hass.services.async_call(
        DOMAIN,
        service,
        fields,
        target={ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )


@pytest.mark.usefixtures("test_entity")
async def test_create_timer_sets_state_and_returns_id(hass: HomeAssistant) -> None:
    """Test creating timers updates the state and returns an id."""
    assert hass.states.get(TEST_ENTITY_ID).state == "0"

    timer_id = await _create_timer(hass, name="Pasta")
    assert timer_id

    assert hass.states.get(TEST_ENTITY_ID).state == "1"

    await _create_timer(hass)
    assert hass.states.get(TEST_ENTITY_ID).state == "2"

    timers = await _get_timers(hass)
    assert len(timers) == 2
    assert {timer["status"] for timer in timers} == {"active"}
    assert timers[0]["name"] == "Pasta"


@pytest.mark.usefixtures("test_entity")
async def test_get_timers_status_filter(hass: HomeAssistant) -> None:
    """Test the get_timers status filter."""
    await _create_timer(hass)
    paused_id = await _create_timer(hass)
    await _call(hass, "pause_timer", timer_id=paused_id)

    assert len(await _get_timers(hass, status=["active"])) == 1
    assert len(await _get_timers(hass, status=["paused"])) == 1
    assert len(await _get_timers(hass, status=["active", "paused"])) == 2
    # A bare status is accepted too, not just a list
    assert len(await _get_timers(hass, status="active")) == 1


@pytest.mark.usefixtures("test_entity")
async def test_pause_and_unpause(hass: HomeAssistant) -> None:
    """Test pausing and resuming a timer."""
    timer_id = await _create_timer(hass)

    await _call(hass, "pause_timer", timer_id=timer_id)
    assert hass.states.get(TEST_ENTITY_ID).state == "0"
    timers = await _get_timers(hass)
    assert timers[0]["status"] == "paused"
    assert timers[0]["finishes_at"] is None

    await _call(hass, "unpause_timer", timer_id=timer_id)
    assert hass.states.get(TEST_ENTITY_ID).state == "1"
    timers = await _get_timers(hass)
    assert timers[0]["status"] == "active"
    assert timers[0]["finishes_at"] is not None


@pytest.mark.usefixtures("test_entity")
async def test_cancel_timer_archives_timer(hass: HomeAssistant) -> None:
    """Test cancelling a timer retains it as cancelled."""
    timer_id = await _create_timer(hass)
    await _call(hass, "cancel_timer", timer_id=timer_id)

    assert hass.states.get(TEST_ENTITY_ID).state == "0"
    timers = await _get_timers(hass)
    assert len(timers) == 1
    assert timers[0]["status"] == "cancelled"


@pytest.mark.usefixtures("test_entity")
async def test_finish_timer_archives_as_finished(hass: HomeAssistant) -> None:
    """Test the finish_timer action reaches the entity."""
    timer_id = await _create_timer(hass, duration=3600)

    await _call(hass, "finish_timer", timer_id=timer_id)

    assert hass.states.get(TEST_ENTITY_ID).state == "0"
    timers = await _get_timers(hass)
    assert len(timers) == 1
    assert timers[0]["status"] == "finished"
    assert timers[0]["ended_at"] is not None
    assert timers[0]["finishes_at"] is None
    assert timers[0]["remaining"] == 0


@pytest.mark.usefixtures("test_entity")
async def test_remove_timer(hass: HomeAssistant) -> None:
    """Test removing a single timer regardless of status."""
    timer_id = await _create_timer(hass)
    await _call(hass, "remove_timer", timer_id=timer_id)

    assert hass.states.get(TEST_ENTITY_ID).state == "0"
    assert await _get_timers(hass) == []


@pytest.mark.usefixtures("test_entity")
async def test_timer_not_found(hass: HomeAssistant) -> None:
    """Test acting on an unknown timer id raises."""
    with pytest.raises(ServiceValidationError):
        await _call(hass, "pause_timer", timer_id="does-not-exist")


@pytest.mark.parametrize(
    "service",
    [
        pytest.param("finish_timer", id="finish_timer"),
        pytest.param("remove_timer", id="remove_timer"),
    ],
)
async def test_unsupported_service_raises(hass: HomeAssistant, service: str) -> None:
    """Test services are rejected when the entity does not support them."""
    entity = MockTimerListEntity()
    entity.entity_id = TEST_ENTITY_ID
    entity._attr_supported_features = TimerListEntityFeature.CREATE_TIMER
    await create_mock_platform(hass, [entity])

    timer_id = await _create_timer(hass)
    with pytest.raises(HomeAssistantError):
        await _call(hass, service, timer_id=timer_id)


@pytest.mark.usefixtures("test_entity")
async def test_websocket_subscribe(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test subscribing to timer changes with an initial snapshot."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "timer_list/item/subscribe", "entity_id": TEST_ENTITY_ID}
    )
    msg = await client.receive_json()
    assert msg["success"]

    msg = await client.receive_json()
    assert msg["event"] == {"type": "timers", "timers": []}

    timer_id = await _create_timer(hass, name="Pasta")
    msg = await client.receive_json()
    assert msg["event"]["type"] == "change"
    assert msg["event"]["event_type"] == "created"
    assert msg["event"]["timer"]["timer_id"] == timer_id
    assert msg["event"]["timer"]["name"] == "Pasta"

    await _call(hass, "pause_timer", timer_id=timer_id)
    msg = await client.receive_json()
    assert msg["event"]["event_type"] == "paused"
    assert "delta" not in msg["event"]

    await _call(hass, "subtract_time", timer_id=timer_id, duration={"seconds": 5})
    msg = await client.receive_json()
    assert msg["event"]["event_type"] == "time_changed"
    assert msg["event"]["delta"] == -5.0

    await _call(hass, "cancel_timer", timer_id=timer_id)
    msg = await client.receive_json()
    assert msg["event"]["event_type"] == "cancelled"


@pytest.mark.usefixtures("test_entity")
async def test_websocket_list(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the one-shot websocket list command."""
    await _create_timer(hass, name="Pasta")

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "timer_list/item/list", "entity_id": TEST_ENTITY_ID}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["timers"]) == 1
    assert msg["result"]["timers"][0]["name"] == "Pasta"


@pytest.mark.usefixtures("test_entity")
@pytest.mark.parametrize(
    "command",
    [
        pytest.param("timer_list/item/subscribe", id="subscribe"),
        pytest.param("timer_list/item/list", id="list"),
    ],
)
async def test_websocket_unknown_entity(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    command: str,
) -> None:
    """Test addressing an entity that does not exist."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": command, "entity_id": "timer_list.unknown"})
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"


async def test_async_get_timer_list_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test resolving the timer list entity belonging to a device."""
    entity = MockTimerListEntity()
    config_entry = await create_mock_platform(hass, [entity])
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(TEST_DOMAIN, "satellite")},
    )

    assert async_get_timer_list_entity(hass, "unknown-device") is None
    assert async_get_timer_list_entity(hass, device.id) is None

    entity_registry.async_update_entity(TEST_ENTITY_ID, device_id=device.id)
    assert async_get_timer_list_entity(hass, device.id) is entity


@pytest.mark.usefixtures("test_entity")
@pytest.mark.parametrize(
    "command",
    [
        pytest.param("timer_list/item/subscribe", id="subscribe"),
        pytest.param("timer_list/item/list", id="list"),
    ],
)
async def test_websocket_requires_read_permission(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
    command: str,
) -> None:
    """Test a user without read access cannot see another entity's timers."""
    await _create_timer(hass, name="Pasta")
    hass_admin_user.mock_policy({"entities": {"entity_ids": {TEST_ENTITY_ID: False}}})

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": command, "entity_id": TEST_ENTITY_ID})

    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"
