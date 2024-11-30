"""The lock tests for the yale platform."""

import datetime

from aiohttp import ClientResponseError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion
from yalexs.manager.activity import INITIAL_LOCK_RESYNC_TIME

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.util.dt as dt_util

from .mocks import (
    _create_yale_with_devices,
    _mock_activities_from_fixture,
    _mock_doorsense_enabled_yale_lock_detail,
    _mock_lock_from_fixture,
    _mock_lock_with_unlatch,
    _mock_operative_yale_lock_detail,
)

from tests.common import async_fire_time_changed


async def test_lock_device_registry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test creation of a lock with doorsense and bridge ands up in the registry."""
    lock_one = await _mock_doorsense_enabled_yale_lock_detail(hass)
    await _create_yale_with_devices(hass, [lock_one])

    reg_device = device_registry.async_get_device(
        identifiers={("yale", "online_with_doorsense")}
    )
    assert reg_device == snapshot


async def test_lock_changed_by(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge."""
    lock_one = await _mock_doorsense_enabled_yale_lock_detail(hass)

    activities = await _mock_activities_from_fixture(hass, "get_activity.lock.json")
    await _create_yale_with_devices(hass, [lock_one], activities=activities)

    lock_state = hass.states.get("lock.online_with_doorsense_name")
    assert lock_state.state == LockState.LOCKED
    assert lock_state.attributes["changed_by"] == "Your favorite elven princess"


async def test_state_locking(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge that is locking."""
    lock_one = await _mock_doorsense_enabled_yale_lock_detail(hass)

    activities = await _mock_activities_from_fixture(hass, "get_activity.locking.json")
    await _create_yale_with_devices(hass, [lock_one], activities=activities)

    assert hass.states.get("lock.online_with_doorsense_name").state == LockState.LOCKING


async def test_state_unlocking(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge that is unlocking."""
    lock_one = await _mock_doorsense_enabled_yale_lock_detail(hass)

    activities = await _mock_activities_from_fixture(
        hass, "get_activity.unlocking.json"
    )
    await _create_yale_with_devices(hass, [lock_one], activities=activities)

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")

    assert lock_online_with_doorsense_name.state == LockState.UNLOCKING


async def test_state_jammed(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge that is jammed."""
    lock_one = await _mock_doorsense_enabled_yale_lock_detail(hass)

    activities = await _mock_activities_from_fixture(hass, "get_activity.jammed.json")
    await _create_yale_with_devices(hass, [lock_one], activities=activities)

    assert hass.states.get("lock.online_with_doorsense_name").state == LockState.JAMMED


async def test_one_lock_operation(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test creation of a lock with doorsense and bridge."""
    lock_one = await _mock_doorsense_enabled_yale_lock_detail(hass)
    await _create_yale_with_devices(hass, [lock_one])

    lock_state = hass.states.get("lock.online_with_doorsense_name")

    assert lock_state.state == LockState.LOCKED

    assert lock_state.attributes["battery_level"] == 92
    assert lock_state.attributes["friendly_name"] == "online_with_doorsense Name"

    data = {ATTR_ENTITY_ID: "lock.online_with_doorsense_name"}
    await hass.services.async_call(LOCK_DOMAIN, SERVICE_UNLOCK, data, blocking=True)

    lock_state = hass.states.get("lock.online_with_doorsense_name")
    assert lock_state.state == LockState.UNLOCKED

    assert lock_state.attributes["battery_level"] == 92
    assert lock_state.attributes["friendly_name"] == "online_with_doorsense Name"

    await hass.services.async_call(LOCK_DOMAIN, SERVICE_LOCK, data, blocking=True)

    lock_state = hass.states.get("lock.online_with_doorsense_name")
    assert lock_state.state == LockState.LOCKED

    # No activity means it will be unavailable until the activity feed has data
    assert entity_registry.async_get("sensor.online_with_doorsense_name_operator")
    operator_state = hass.states.get("sensor.online_with_doorsense_name_operator")
    assert operator_state.state == STATE_UNKNOWN


async def test_open_lock_operation(hass: HomeAssistant) -> None:
    """Test open lock operation using the open service."""
    lock_with_unlatch = await _mock_lock_with_unlatch(hass)
    await _create_yale_with_devices(hass, [lock_with_unlatch])

    assert hass.states.get("lock.online_with_unlatch_name").state == LockState.LOCKED

    data = {ATTR_ENTITY_ID: "lock.online_with_unlatch_name"}
    await hass.services.async_call(LOCK_DOMAIN, SERVICE_OPEN, data, blocking=True)

    assert hass.states.get("lock.online_with_unlatch_name").state == LockState.UNLOCKED


async def test_open_lock_operation_socketio_connected(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test open lock operation using the open service when socketio is connected."""
    lock_with_unlatch = await _mock_lock_with_unlatch(hass)
    assert lock_with_unlatch.pubsub_channel == "pubsub"

    _, socketio = await _create_yale_with_devices(hass, [lock_with_unlatch])
    socketio.connected = True

    assert hass.states.get("lock.online_with_unlatch_name").state == LockState.LOCKED

    data = {ATTR_ENTITY_ID: "lock.online_with_unlatch_name"}
    await hass.services.async_call(LOCK_DOMAIN, SERVICE_OPEN, data, blocking=True)

    listener = list(socketio._listeners)[0]
    listener(
        lock_with_unlatch.device_id,
        dt_util.utcnow() + datetime.timedelta(seconds=2),
        {
            "status": "kAugLockState_Unlocked",
        },
    )

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert hass.states.get("lock.online_with_unlatch_name").state == LockState.UNLOCKED
    await hass.async_block_till_done()


async def test_one_lock_operation_socketio_connected(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test lock and unlock operations are async when socketio is connected."""
    lock_one = await _mock_doorsense_enabled_yale_lock_detail(hass)
    assert lock_one.pubsub_channel == "pubsub"
    states = hass.states

    _, socketio = await _create_yale_with_devices(hass, [lock_one])
    socketio.connected = True

    lock_state = hass.states.get("lock.online_with_doorsense_name")
    assert lock_state.state == LockState.LOCKED
    assert lock_state.attributes["battery_level"] == 92
    assert lock_state.attributes["friendly_name"] == "online_with_doorsense Name"

    data = {ATTR_ENTITY_ID: "lock.online_with_doorsense_name"}
    await hass.services.async_call(LOCK_DOMAIN, SERVICE_UNLOCK, data, blocking=True)

    listener = list(socketio._listeners)[0]
    listener(
        lock_one.device_id,
        dt_util.utcnow() + datetime.timedelta(seconds=1),
        {
            "status": "kAugLockState_Unlocked",
        },
    )

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    lock_state = states.get("lock.online_with_doorsense_name")
    assert lock_state.state == LockState.UNLOCKED
    assert lock_state.attributes["battery_level"] == 92
    assert lock_state.attributes["friendly_name"] == "online_with_doorsense Name"

    await hass.services.async_call(LOCK_DOMAIN, SERVICE_LOCK, data, blocking=True)

    listener(
        lock_one.device_id,
        dt_util.utcnow() + datetime.timedelta(seconds=2),
        {
            "status": "kAugLockState_Locked",
        },
    )

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert states.get("lock.online_with_doorsense_name").state == LockState.LOCKED

    # No activity means it will be unavailable until the activity feed has data
    assert entity_registry.async_get("sensor.online_with_doorsense_name_operator")
    assert (
        states.get("sensor.online_with_doorsense_name_operator").state == STATE_UNKNOWN
    )

    freezer.tick(INITIAL_LOCK_RESYNC_TIME)

    listener(
        lock_one.device_id,
        dt_util.utcnow() + datetime.timedelta(seconds=2),
        {
            "status": "kAugLockState_Unlocked",
        },
    )

    await hass.async_block_till_done()

    assert states.get("lock.online_with_doorsense_name").state == LockState.UNLOCKED


async def test_lock_jammed(hass: HomeAssistant) -> None:
    """Test lock gets jammed on unlock."""

    def _unlock_return_activities_side_effect(access_token, device_id):
        raise ClientResponseError(None, None, status=531)

    lock_one = await _mock_doorsense_enabled_yale_lock_detail(hass)
    await _create_yale_with_devices(
        hass,
        [lock_one],
        api_call_side_effects={
            "unlock_return_activities": _unlock_return_activities_side_effect
        },
    )

    states = hass.states
    lock_state = states.get("lock.online_with_doorsense_name")
    assert lock_state.state == LockState.LOCKED
    assert lock_state.attributes["battery_level"] == 92
    assert lock_state.attributes["friendly_name"] == "online_with_doorsense Name"

    data = {ATTR_ENTITY_ID: "lock.online_with_doorsense_name"}
    await hass.services.async_call(LOCK_DOMAIN, SERVICE_UNLOCK, data, blocking=True)

    assert states.get("lock.online_with_doorsense_name").state == LockState.JAMMED


async def test_lock_throws_exception_on_unknown_status_code(
    hass: HomeAssistant,
) -> None:
    """Test lock throws exception."""

    def _unlock_return_activities_side_effect(access_token, device_id):
        raise ClientResponseError(None, None, status=500)

    lock_one = await _mock_doorsense_enabled_yale_lock_detail(hass)
    await _create_yale_with_devices(
        hass,
        [lock_one],
        api_call_side_effects={
            "unlock_return_activities": _unlock_return_activities_side_effect
        },
    )

    lock_state = hass.states.get("lock.online_with_doorsense_name")
    assert lock_state.state == LockState.LOCKED
    assert lock_state.attributes["battery_level"] == 92
    assert lock_state.attributes["friendly_name"] == "online_with_doorsense Name"

    data = {ATTR_ENTITY_ID: "lock.online_with_doorsense_name"}
    with pytest.raises(ClientResponseError):
        await hass.services.async_call(LOCK_DOMAIN, SERVICE_UNLOCK, data, blocking=True)


async def test_one_lock_unknown_state(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge."""
    lock_one = await _mock_lock_from_fixture(
        hass,
        "get_lock.online.unknown_state.json",
    )
    await _create_yale_with_devices(hass, [lock_one])

    assert hass.states.get("lock.brokenid_name").state == STATE_UNKNOWN


async def test_lock_bridge_offline(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge that goes offline."""
    lock_one = await _mock_doorsense_enabled_yale_lock_detail(hass)

    activities = await _mock_activities_from_fixture(
        hass, "get_activity.bridge_offline.json"
    )
    await _create_yale_with_devices(hass, [lock_one], activities=activities)

    states = hass.states
    assert states.get("lock.online_with_doorsense_name").state == STATE_UNAVAILABLE


async def test_lock_bridge_online(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge that goes offline."""
    lock_one = await _mock_doorsense_enabled_yale_lock_detail(hass)

    activities = await _mock_activities_from_fixture(
        hass, "get_activity.bridge_online.json"
    )
    await _create_yale_with_devices(hass, [lock_one], activities=activities)

    states = hass.states
    assert states.get("lock.online_with_doorsense_name").state == LockState.LOCKED


async def test_lock_update_via_socketio(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge."""
    lock_one = await _mock_doorsense_enabled_yale_lock_detail(hass)
    assert lock_one.pubsub_channel == "pubsub"

    activities = await _mock_activities_from_fixture(hass, "get_activity.lock.json")
    config_entry, socketio = await _create_yale_with_devices(
        hass, [lock_one], activities=activities
    )
    socketio.connected = True
    states = hass.states

    assert states.get("lock.online_with_doorsense_name").state == LockState.LOCKED

    listener = list(socketio._listeners)[0]
    listener(
        lock_one.device_id,
        dt_util.utcnow(),
        {
            "status": "kAugLockState_Unlocking",
        },
    )

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert states.get("lock.online_with_doorsense_name").state == LockState.UNLOCKING

    listener(
        lock_one.device_id,
        dt_util.utcnow(),
        {
            "status": "kAugLockState_Locking",
        },
    )

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert states.get("lock.online_with_doorsense_name").state == LockState.LOCKING

    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(seconds=30))
    await hass.async_block_till_done()
    assert states.get("lock.online_with_doorsense_name").state == LockState.LOCKING

    socketio.connected = True
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(seconds=30))
    await hass.async_block_till_done()
    assert states.get("lock.online_with_doorsense_name").state == LockState.LOCKING

    # Ensure socketio status is always preserved
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=2))
    await hass.async_block_till_done()
    assert states.get("lock.online_with_doorsense_name").state == LockState.LOCKING

    listener(
        lock_one.device_id,
        dt_util.utcnow() + datetime.timedelta(seconds=2),
        {
            "status": "kAugLockState_Unlocking",
        },
    )

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert states.get("lock.online_with_doorsense_name").state == LockState.UNLOCKING

    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=4))
    await hass.async_block_till_done()
    assert states.get("lock.online_with_doorsense_name").state == LockState.UNLOCKING

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_open_throws_hass_service_not_supported_error(
    hass: HomeAssistant,
) -> None:
    """Test open throws correct error on entity does not support this service error."""
    mocked_lock_detail = await _mock_operative_yale_lock_detail(hass)
    await _create_yale_with_devices(hass, [mocked_lock_detail])
    data = {ATTR_ENTITY_ID: "lock.a6697750d607098bae8d6baa11ef8063_name"}
    with pytest.raises(HomeAssistantError, match="does not support this service"):
        await hass.services.async_call(LOCK_DOMAIN, SERVICE_OPEN, data, blocking=True)
