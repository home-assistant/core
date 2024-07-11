"""Test Matter locks."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest

from homeassistant.components.lock import (
    STATE_LOCKED,
    STATE_UNLOCKED,
    LockEntityFeature,
)
from homeassistant.const import ATTR_CODE, STATE_LOCKING, STATE_OPENING, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.entity_registry as er

from .common import set_node_attribute, trigger_subscription_callback


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_lock(
    hass: HomeAssistant,
    matter_client: MagicMock,
    door_lock: MatterNode,
) -> None:
    """Test door lock."""
    await hass.services.async_call(
        "lock",
        "unlock",
        {
            "entity_id": "lock.mock_door_lock_lock",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=door_lock.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.UnlockDoor(),
        timed_request_timeout_ms=1000,
    )
    matter_client.send_device_command.reset_mock()

    await hass.services.async_call(
        "lock",
        "lock",
        {
            "entity_id": "lock.mock_door_lock_lock",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=door_lock.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.LockDoor(),
        timed_request_timeout_ms=1000,
    )
    matter_client.send_device_command.reset_mock()

    await hass.async_block_till_done()
    state = hass.states.get("lock.mock_door_lock_lock")
    assert state
    assert state.state == STATE_LOCKING

    set_node_attribute(door_lock, 1, 257, 0, 0)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("lock.mock_door_lock_lock")
    assert state
    assert state.state == STATE_UNLOCKED

    set_node_attribute(door_lock, 1, 257, 0, 2)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("lock.mock_door_lock_lock")
    assert state
    assert state.state == STATE_UNLOCKED

    set_node_attribute(door_lock, 1, 257, 0, 0)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("lock.mock_door_lock_lock")
    assert state
    assert state.state == STATE_UNLOCKED

    set_node_attribute(door_lock, 1, 257, 0, None)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("lock.mock_door_lock_lock")
    assert state
    assert state.state == STATE_UNKNOWN


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_lock_requires_pin(
    hass: HomeAssistant,
    matter_client: MagicMock,
    door_lock: MatterNode,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test door lock with PINCode."""

    code = "1234567"

    # set RequirePINforRemoteOperation
    set_node_attribute(door_lock, 1, 257, 51, True)
    # set door state to unlocked
    set_node_attribute(door_lock, 1, 257, 0, 2)

    await trigger_subscription_callback(hass, matter_client)
    with pytest.raises(ServiceValidationError):
        # Lock door using invalid code format
        await hass.services.async_call(
            "lock",
            "lock",
            {"entity_id": "lock.mock_door_lock_lock", ATTR_CODE: "1234"},
            blocking=True,
        )

    # Lock door using valid code
    await trigger_subscription_callback(hass, matter_client)
    await hass.services.async_call(
        "lock",
        "lock",
        {"entity_id": "lock.mock_door_lock_lock", ATTR_CODE: code},
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=door_lock.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.LockDoor(code.encode()),
        timed_request_timeout_ms=1000,
    )

    # Lock door using default code
    default_code = "7654321"
    entity_registry.async_update_entity_options(
        "lock.mock_door_lock_lock", "lock", {"default_code": default_code}
    )
    await trigger_subscription_callback(hass, matter_client)
    await hass.services.async_call(
        "lock",
        "lock",
        {"entity_id": "lock.mock_door_lock_lock"},
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 2
    assert matter_client.send_device_command.call_args == call(
        node_id=door_lock.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.LockDoor(default_code.encode()),
        timed_request_timeout_ms=1000,
    )


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_lock_with_unbolt(
    hass: HomeAssistant,
    matter_client: MagicMock,
    door_lock_with_unbolt: MatterNode,
) -> None:
    """Test door lock."""
    state = hass.states.get("lock.mock_door_lock_lock")
    assert state
    assert state.state == STATE_LOCKED
    assert state.attributes["supported_features"] & LockEntityFeature.OPEN
    # test unlock/unbolt
    await hass.services.async_call(
        "lock",
        "unlock",
        {
            "entity_id": "lock.mock_door_lock_lock",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    # unlock should unbolt on a lock with unbolt feature
    assert matter_client.send_device_command.call_args == call(
        node_id=door_lock_with_unbolt.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.UnboltDoor(),
        timed_request_timeout_ms=1000,
    )
    matter_client.send_device_command.reset_mock()
    # test open / unlatch
    await hass.services.async_call(
        "lock",
        "open",
        {
            "entity_id": "lock.mock_door_lock_lock",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=door_lock_with_unbolt.node_id,
        endpoint_id=1,
        command=clusters.DoorLock.Commands.UnlockDoor(),
        timed_request_timeout_ms=1000,
    )

    await hass.async_block_till_done()
    state = hass.states.get("lock.mock_door_lock_lock")
    assert state
    assert state.state == STATE_OPENING

    set_node_attribute(door_lock_with_unbolt, 1, 257, 3, 0)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("lock.mock_door_lock_lock")
    assert state
    assert state.state == STATE_LOCKED
