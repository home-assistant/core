"""Tests for the Timer list integration."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.timer_list import TimerListEntity
from homeassistant.components.timer_list.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import async_fire_time_changed
from tests.typing import WebSocketGenerator

TEST_ENTITY_ID = "timer_list.timers"


async def _start_timer(
    hass: HomeAssistant,
    *,
    duration: int = 60,
    name: str | None = None,
) -> str:
    """Start a timer and return its id."""
    data: dict[str, Any] = {"duration": {"seconds": duration}}
    if name is not None:
        data[ATTR_NAME] = name
    result = await hass.services.async_call(
        DOMAIN,
        "start_timer",
        data,
        target={ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    return result[TEST_ENTITY_ID]["timer_id"]


async def _get_timers(
    hass: HomeAssistant, status: list[str] | None = None
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
async def test_start_timer_sets_state_and_returns_id(hass: HomeAssistant) -> None:
    """Test starting timers updates the state and returns an id."""
    assert hass.states.get(TEST_ENTITY_ID).state == "0"

    timer_id = await _start_timer(hass, name="Pasta")
    assert timer_id

    assert hass.states.get(TEST_ENTITY_ID).state == "1"

    await _start_timer(hass)
    assert hass.states.get(TEST_ENTITY_ID).state == "2"

    timers = await _get_timers(hass)
    assert len(timers) == 2
    assert {timer["status"] for timer in timers} == {"active"}
    assert timers[0]["name"] == "Pasta"


@pytest.mark.usefixtures("test_entity")
async def test_get_timers_status_filter(hass: HomeAssistant) -> None:
    """Test the get_timers status filter."""
    await _start_timer(hass)
    paused_id = await _start_timer(hass)
    await _call(hass, "pause_timer", timer_id=paused_id)

    assert len(await _get_timers(hass, status=["active"])) == 1
    assert len(await _get_timers(hass, status=["paused"])) == 1
    assert len(await _get_timers(hass, status=["active", "paused"])) == 2


@pytest.mark.usefixtures("test_entity")
async def test_timer_finishes_and_is_archived(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a finished timer is archived as ``finished``."""
    await _start_timer(hass, duration=60)

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == "0"
    timers = await _get_timers(hass)
    assert len(timers) == 1
    assert timers[0]["status"] == "finished"
    assert timers[0]["finished_at"] is not None


@pytest.mark.usefixtures("test_entity")
async def test_pause_and_unpause(hass: HomeAssistant) -> None:
    """Test pausing and resuming a timer."""
    timer_id = await _start_timer(hass)

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
async def test_add_and_remove_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test adding and removing time on a timer."""
    timer_id = await _start_timer(hass, duration=60)

    await _call(hass, "add_time", timer_id=timer_id, duration={"seconds": 60})
    assert (await _get_timers(hass))[0]["remaining"] == pytest.approx(120, abs=1)

    await _call(hass, "remove_time", timer_id=timer_id, duration={"seconds": 90})
    assert (await _get_timers(hass))[0]["remaining"] == pytest.approx(30, abs=1)


@pytest.mark.usefixtures("test_entity")
async def test_remove_time_finishes_timer(hass: HomeAssistant) -> None:
    """Test removing more time than remaining finishes the timer immediately."""
    timer_id = await _start_timer(hass, duration=60)

    await _call(hass, "remove_time", timer_id=timer_id, duration={"seconds": 120})

    assert hass.states.get(TEST_ENTITY_ID).state == "0"
    assert (await _get_timers(hass))[0]["status"] == "finished"


@pytest.mark.usefixtures("test_entity")
async def test_cancel_timer_archives_timer(hass: HomeAssistant) -> None:
    """Test cancelling a timer retains it as cancelled."""
    timer_id = await _start_timer(hass)
    await _call(hass, "cancel_timer", timer_id=timer_id)

    assert hass.states.get(TEST_ENTITY_ID).state == "0"
    timers = await _get_timers(hass)
    assert len(timers) == 1
    assert timers[0]["status"] == "cancelled"


@pytest.mark.usefixtures("test_entity")
async def test_archive_limit_evicts_oldest(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test only the 10 most recently archived timers are retained."""
    timer_ids = []
    for _ in range(11):
        timer_id = await _start_timer(hass)
        await _call(hass, "cancel_timer", timer_id=timer_id)
        timer_ids.append(timer_id)
        freezer.tick(timedelta(seconds=1))

    timers = await _get_timers(hass)
    assert len(timers) == 10
    archived_ids = {timer["timer_id"] for timer in timers}
    assert timer_ids[0] not in archived_ids
    assert set(timer_ids[1:]) == archived_ids


@pytest.mark.usefixtures("test_entity")
async def test_remove_timer(hass: HomeAssistant) -> None:
    """Test removing a single timer regardless of status."""
    timer_id = await _start_timer(hass)
    await _call(hass, "remove_timer", timer_id=timer_id)

    assert hass.states.get(TEST_ENTITY_ID).state == "0"
    assert await _get_timers(hass) == []


@pytest.mark.usefixtures("test_entity")
async def test_timer_not_found(hass: HomeAssistant) -> None:
    """Test acting on an unknown timer id raises."""
    with pytest.raises(ServiceValidationError):
        await _call(hass, "pause_timer", timer_id="does-not-exist")


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

    timer_id = await _start_timer(hass, name="Pasta")
    msg = await client.receive_json()
    assert msg["event"]["type"] == "change"
    assert msg["event"]["event_type"] == "started"
    assert msg["event"]["timer"]["timer_id"] == timer_id
    assert msg["event"]["timer"]["name"] == "Pasta"

    await _call(hass, "cancel_timer", timer_id=timer_id)
    msg = await client.receive_json()
    assert msg["event"]["event_type"] == "cancelled"


@pytest.mark.usefixtures("test_entity")
async def test_websocket_list(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the one-shot websocket list command."""
    await _start_timer(hass, name="Pasta")

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "timer_list/item/list", "entity_id": TEST_ENTITY_ID}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["timers"]) == 1
    assert msg["result"]["timers"][0]["name"] == "Pasta"


async def test_websocket_subscribe_unknown_entity(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    test_entity: TimerListEntity,
) -> None:
    """Test subscribing to an entity that does not exist."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "timer_list/item/subscribe", "entity_id": "timer_list.unknown"}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"
