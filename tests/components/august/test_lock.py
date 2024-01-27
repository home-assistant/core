"""The lock tests for the august platform."""
import datetime
from unittest.mock import Mock

from aiohttp import ClientResponseError
import pytest
from yalexs.pubnub_async import AugustPubNub

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    STATE_JAMMED,
    STATE_LOCKING,
    STATE_UNLOCKING,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    STATE_LOCKED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    STATE_UNLOCKED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.util.dt as dt_util

from .mocks import (
    _create_august_with_devices,
    _mock_activities_from_fixture,
    _mock_doorsense_enabled_august_lock_detail,
    _mock_lock_from_fixture,
)

from tests.common import async_fire_time_changed


async def test_lock_device_registry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test creation of a lock with doorsense and bridge ands up in the registry."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)
    await _create_august_with_devices(hass, [lock_one])

    reg_device = device_registry.async_get_device(
        identifiers={("august", "online_with_doorsense")}
    )
    assert reg_device.model == "AUG-MD01"
    assert reg_device.sw_version == "undefined-4.3.0-1.8.14"
    assert reg_device.name == "online_with_doorsense Name"
    assert reg_device.manufacturer == "August Home Inc."


async def test_lock_changed_by(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)

    activities = await _mock_activities_from_fixture(hass, "get_activity.lock.json")
    await _create_august_with_devices(hass, [lock_one], activities=activities)

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")

    assert lock_online_with_doorsense_name.state == STATE_LOCKED

    assert (
        lock_online_with_doorsense_name.attributes.get("changed_by")
        == "Your favorite elven princess"
    )


async def test_state_locking(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge that is locking."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)

    activities = await _mock_activities_from_fixture(hass, "get_activity.locking.json")
    await _create_august_with_devices(hass, [lock_one], activities=activities)

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")

    assert lock_online_with_doorsense_name.state == STATE_LOCKING


async def test_state_unlocking(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge that is unlocking."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)

    activities = await _mock_activities_from_fixture(
        hass, "get_activity.unlocking.json"
    )
    await _create_august_with_devices(hass, [lock_one], activities=activities)

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")

    assert lock_online_with_doorsense_name.state == STATE_UNLOCKING


async def test_state_jammed(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge that is jammed."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)

    activities = await _mock_activities_from_fixture(hass, "get_activity.jammed.json")
    await _create_august_with_devices(hass, [lock_one], activities=activities)

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")

    assert lock_online_with_doorsense_name.state == STATE_JAMMED


async def test_one_lock_operation(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test creation of a lock with doorsense and bridge."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)
    await _create_august_with_devices(hass, [lock_one])

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")

    assert lock_online_with_doorsense_name.state == STATE_LOCKED

    assert lock_online_with_doorsense_name.attributes.get("battery_level") == 92
    assert (
        lock_online_with_doorsense_name.attributes.get("friendly_name")
        == "online_with_doorsense Name"
    )

    data = {ATTR_ENTITY_ID: "lock.online_with_doorsense_name"}
    await hass.services.async_call(LOCK_DOMAIN, SERVICE_UNLOCK, data, blocking=True)
    await hass.async_block_till_done()

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")
    assert lock_online_with_doorsense_name.state == STATE_UNLOCKED

    assert lock_online_with_doorsense_name.attributes.get("battery_level") == 92
    assert (
        lock_online_with_doorsense_name.attributes.get("friendly_name")
        == "online_with_doorsense Name"
    )

    await hass.services.async_call(LOCK_DOMAIN, SERVICE_LOCK, data, blocking=True)
    await hass.async_block_till_done()

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")
    assert lock_online_with_doorsense_name.state == STATE_LOCKED

    # No activity means it will be unavailable until the activity feed has data
    lock_operator_sensor = entity_registry.async_get(
        "sensor.online_with_doorsense_name_operator"
    )
    assert lock_operator_sensor
    assert (
        hass.states.get("sensor.online_with_doorsense_name_operator").state
        == STATE_UNKNOWN
    )


async def test_one_lock_operation_pubnub_connected(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test lock and unlock operations are async when pubnub is connected."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)
    assert lock_one.pubsub_channel == "pubsub"

    pubnub = AugustPubNub()
    await _create_august_with_devices(hass, [lock_one], pubnub=pubnub)
    pubnub.connected = True

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")

    assert lock_online_with_doorsense_name.state == STATE_LOCKED

    assert lock_online_with_doorsense_name.attributes.get("battery_level") == 92
    assert (
        lock_online_with_doorsense_name.attributes.get("friendly_name")
        == "online_with_doorsense Name"
    )

    data = {ATTR_ENTITY_ID: "lock.online_with_doorsense_name"}
    await hass.services.async_call(LOCK_DOMAIN, SERVICE_UNLOCK, data, blocking=True)
    await hass.async_block_till_done()

    pubnub.message(
        pubnub,
        Mock(
            channel=lock_one.pubsub_channel,
            timetoken=(dt_util.utcnow().timestamp() + 1) * 10000000,
            message={
                "status": "kAugLockState_Unlocked",
            },
        ),
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")
    assert lock_online_with_doorsense_name.state == STATE_UNLOCKED

    assert lock_online_with_doorsense_name.attributes.get("battery_level") == 92
    assert (
        lock_online_with_doorsense_name.attributes.get("friendly_name")
        == "online_with_doorsense Name"
    )

    await hass.services.async_call(LOCK_DOMAIN, SERVICE_LOCK, data, blocking=True)
    await hass.async_block_till_done()

    pubnub.message(
        pubnub,
        Mock(
            channel=lock_one.pubsub_channel,
            timetoken=(dt_util.utcnow().timestamp() + 2) * 10000000,
            message={
                "status": "kAugLockState_Locked",
            },
        ),
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")
    assert lock_online_with_doorsense_name.state == STATE_LOCKED

    # No activity means it will be unavailable until the activity feed has data
    lock_operator_sensor = entity_registry.async_get(
        "sensor.online_with_doorsense_name_operator"
    )
    assert lock_operator_sensor
    assert (
        hass.states.get("sensor.online_with_doorsense_name_operator").state
        == STATE_UNKNOWN
    )


async def test_lock_jammed(hass: HomeAssistant) -> None:
    """Test lock gets jammed on unlock."""

    def _unlock_return_activities_side_effect(access_token, device_id):
        raise ClientResponseError(None, None, status=531)

    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)
    await _create_august_with_devices(
        hass,
        [lock_one],
        api_call_side_effects={
            "unlock_return_activities": _unlock_return_activities_side_effect
        },
    )

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")

    assert lock_online_with_doorsense_name.state == STATE_LOCKED

    assert lock_online_with_doorsense_name.attributes.get("battery_level") == 92
    assert (
        lock_online_with_doorsense_name.attributes.get("friendly_name")
        == "online_with_doorsense Name"
    )

    data = {ATTR_ENTITY_ID: "lock.online_with_doorsense_name"}
    await hass.services.async_call(LOCK_DOMAIN, SERVICE_UNLOCK, data, blocking=True)
    await hass.async_block_till_done()

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")
    assert lock_online_with_doorsense_name.state == STATE_JAMMED


async def test_lock_throws_exception_on_unknown_status_code(
    hass: HomeAssistant,
) -> None:
    """Test lock throws exception."""

    def _unlock_return_activities_side_effect(access_token, device_id):
        raise ClientResponseError(None, None, status=500)

    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)
    await _create_august_with_devices(
        hass,
        [lock_one],
        api_call_side_effects={
            "unlock_return_activities": _unlock_return_activities_side_effect
        },
    )

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")

    assert lock_online_with_doorsense_name.state == STATE_LOCKED

    assert lock_online_with_doorsense_name.attributes.get("battery_level") == 92
    assert (
        lock_online_with_doorsense_name.attributes.get("friendly_name")
        == "online_with_doorsense Name"
    )

    data = {ATTR_ENTITY_ID: "lock.online_with_doorsense_name"}
    with pytest.raises(ClientResponseError):
        await hass.services.async_call(LOCK_DOMAIN, SERVICE_UNLOCK, data, blocking=True)
        await hass.async_block_till_done()


async def test_one_lock_unknown_state(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge."""
    lock_one = await _mock_lock_from_fixture(
        hass,
        "get_lock.online.unknown_state.json",
    )
    await _create_august_with_devices(hass, [lock_one])

    lock_brokenid_name = hass.states.get("lock.brokenid_name")

    assert lock_brokenid_name.state == STATE_UNKNOWN


async def test_lock_bridge_offline(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge that goes offline."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)

    activities = await _mock_activities_from_fixture(
        hass, "get_activity.bridge_offline.json"
    )
    await _create_august_with_devices(hass, [lock_one], activities=activities)

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")

    assert lock_online_with_doorsense_name.state == STATE_UNAVAILABLE


async def test_lock_bridge_online(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge that goes offline."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)

    activities = await _mock_activities_from_fixture(
        hass, "get_activity.bridge_online.json"
    )
    await _create_august_with_devices(hass, [lock_one], activities=activities)

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")

    assert lock_online_with_doorsense_name.state == STATE_LOCKED


async def test_lock_update_via_pubnub(hass: HomeAssistant) -> None:
    """Test creation of a lock with doorsense and bridge."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)
    assert lock_one.pubsub_channel == "pubsub"
    pubnub = AugustPubNub()

    activities = await _mock_activities_from_fixture(hass, "get_activity.lock.json")
    config_entry = await _create_august_with_devices(
        hass, [lock_one], activities=activities, pubnub=pubnub
    )
    pubnub.connected = True

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")

    assert lock_online_with_doorsense_name.state == STATE_LOCKED

    pubnub.message(
        pubnub,
        Mock(
            channel=lock_one.pubsub_channel,
            timetoken=dt_util.utcnow().timestamp() * 10000000,
            message={
                "status": "kAugLockState_Unlocking",
            },
        ),
    )

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")
    assert lock_online_with_doorsense_name.state == STATE_UNLOCKING

    pubnub.message(
        pubnub,
        Mock(
            channel=lock_one.pubsub_channel,
            timetoken=(dt_util.utcnow().timestamp() + 1) * 10000000,
            message={
                "status": "kAugLockState_Locking",
            },
        ),
    )

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")
    assert lock_online_with_doorsense_name.state == STATE_LOCKING

    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(seconds=30))
    await hass.async_block_till_done()
    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")
    assert lock_online_with_doorsense_name.state == STATE_LOCKING

    pubnub.connected = True
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(seconds=30))
    await hass.async_block_till_done()
    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")
    assert lock_online_with_doorsense_name.state == STATE_LOCKING

    # Ensure pubnub status is always preserved
    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=2))
    await hass.async_block_till_done()
    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")
    assert lock_online_with_doorsense_name.state == STATE_LOCKING

    pubnub.message(
        pubnub,
        Mock(
            channel=lock_one.pubsub_channel,
            timetoken=(dt_util.utcnow().timestamp() + 2) * 10000000,
            message={
                "status": "kAugLockState_Unlocking",
            },
        ),
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")
    assert lock_online_with_doorsense_name.state == STATE_UNLOCKING

    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=4))
    await hass.async_block_till_done()
    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")
    assert lock_online_with_doorsense_name.state == STATE_UNLOCKING

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
