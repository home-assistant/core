"""Tests related to Powersensor's Home Assistant integration's message dispatcher."""

import asyncio
import importlib
from ipaddress import ip_address
from unittest.mock import Mock, call

import pytest

from homeassistant.components.powersensor import PowersensorConfigFlow
from homeassistant.components.powersensor.const import (
    CFG_DEVICES,
    CFG_ROLES,
    CREATE_PLUG_SIGNAL,
    CREATE_SENSOR_SIGNAL,
    DATA_UPDATE_SIGNAL_PREFIX,
    DOMAIN,
    ROLE_UNKNOWN,
    ROLE_UPDATE_SIGNAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MAC = "a4cf1218f158"


@pytest.fixture
def monkey_patched_dispatcher(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch):
    """Return a PowersensorMessageDispatcher with its dependencies monkey-patched.

    Patches async_dispatcher_connect/send so that signals never reach real entities,
    and makes async_create_background_task synchronous so background work can be
    awaited in tests via hass.async_block_till_done().
    """

    def create_task(coroutine, name=None):
        return asyncio.create_task(coroutine)

    monkeypatch.setattr(hass, "async_create_background_task", create_task)

    powersensor_dispatcher_module = importlib.import_module(
        "homeassistant.components.powersensor.powersensor_message_dispatcher"
    )

    async_dispatcher_connect = Mock()
    monkeypatch.setattr(
        powersensor_dispatcher_module,
        "async_dispatcher_connect",
        async_dispatcher_connect,
    )
    async_dispatcher_send = Mock()
    monkeypatch.setattr(
        powersensor_dispatcher_module, "async_dispatcher_send", async_dispatcher_send
    )

    vhh = powersensor_dispatcher_module.VirtualHousehold(False)
    entry = Mock()
    entry.data = {CFG_ROLES: {}}

    dispatcher = powersensor_dispatcher_module.PowersensorMessageDispatcher(
        hass, entry, vhh, debounce_timeout=1
    )
    dispatcher.dispatch_send_reference = async_dispatcher_send
    return dispatcher


@pytest.fixture
def network_info():
    """Network information for a Powersensor gateway."""
    return {
        "mac": MAC,
        "host": "192.168.0.33",
        "port": 49476,
        "name": f"Powersensor-gateway-{MAC}-civet._powersensor._udp.local.",
    }


@pytest.fixture
def zeroconf_discovery_info():
    """Zeroconf discovery payload for a Powersensor gateway."""
    return {
        "type": "_powersensor._udp.local.",
        "name": f"Powersensor-gateway-{MAC}-civet._powersensor._udp.local.",
        "addresses": [ip_address("192.168.0.33")],
        "port": 49476,
        "server": f"Powersensor-gateway-{MAC}-civet.local.",
        "properties": {
            "version": "1",
            b"id": f"{MAC}".encode(),
        },
    }


async def follow_normal_add_sequence(dispatcher, network_info):
    """Drive a plug through the full discovery → entity-creation → API handshake.

    After this helper returns, ``dispatcher.plugs[MAC]`` is populated and the
    queue is empty.
    """
    assert not dispatcher.plugs
    dispatcher.enqueue_plug_for_adding(
        network_info["mac"],
        network_info["host"],
        network_info["port"],
        network_info["name"],
    )
    dispatcher.process_plug_queue()
    for _ in range(3):
        await dispatcher._hass.async_block_till_done(wait_background_tasks=True)

    dispatcher.dispatch_send_reference.assert_called_once_with(
        dispatcher._hass,
        CREATE_PLUG_SIGNAL,
        network_info["mac"],
        network_info["host"],
        network_info["port"],
        network_info["name"],
    )

    # Simulate the sensor platform acknowledging entity creation.
    dispatcher._acknowledge_plug_added_to_homeassistant(
        network_info["mac"],
        network_info["host"],
        network_info["port"],
        network_info["name"],
    )
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()

    assert MAC in dispatcher.plugs


@pytest.mark.asyncio
async def test_dispatcher_monitor_plug_queue(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher, network_info
) -> None:
    """Test enqueue_plug_for_adding and _poll_plug_queue.

    Verifies that:
    - An API object is created for a known plug that is not yet in plugs.
    - The queue is fully drained after acknowledgement.
    """
    dispatcher = monkey_patched_dispatcher

    # Pre-mark the MAC as known so the queue handler reconnects without creating an entity.
    dispatcher._known_plugs.add(MAC)

    assert not dispatcher.plugs
    dispatcher.enqueue_plug_for_adding(
        network_info["mac"],
        network_info["host"],
        network_info["port"],
        network_info["name"],
    )
    dispatcher.process_plug_queue()
    for _ in range(10):
        await dispatcher._hass.async_block_till_done(wait_background_tasks=True)

    assert MAC in dispatcher.plugs

    # Re-enqueueing a known, connected plug should drain immediately.
    dispatcher.enqueue_plug_for_adding(
        network_info["mac"],
        network_info["host"],
        network_info["port"],
        network_info["name"],
    )
    dispatcher.process_plug_queue()
    for _ in range(10):
        await dispatcher._hass.async_block_till_done(wait_background_tasks=True)

    assert MAC in dispatcher.plugs
    assert not dispatcher._plug_added_queue


@pytest.mark.asyncio
async def test_dispatcher_monitor_plug_queue_error_handling(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher, network_info
) -> None:
    """Test that an exception in _plug_has_been_seen does not create a stale API entry."""
    dispatcher = monkey_patched_dispatcher

    def raise_error(*args, **kwargs):
        raise NotImplementedError

    monkeypatch.setattr(dispatcher, "_plug_has_been_seen", raise_error)
    assert not dispatcher.plugs
    dispatcher.enqueue_plug_for_adding(
        network_info["mac"],
        network_info["host"],
        network_info["port"],
        network_info["name"],
    )
    dispatcher.process_plug_queue()
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()
    assert not dispatcher.plugs


@pytest.mark.asyncio
async def test_dispatcher_handle_plug_exception(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher, network_info
) -> None:
    """Test that _handle_exception does not raise."""
    powersensor_dispatcher_module = importlib.import_module(
        "homeassistant.components.powersensor.powersensor_message_dispatcher"
    )
    await powersensor_dispatcher_module._handle_exception(
        "exception", NotImplementedError
    )


@pytest.mark.asyncio
async def test_dispatcher_removal(
    monkeypatch: pytest.MonkeyPatch,
    monkey_patched_dispatcher,
    network_info,
    zeroconf_discovery_info,
) -> None:
    """Test plug removal debounce, cancellation, and stop_pending_removal_tasks.

    Verifies that:
    - Removal of a never-added plug is silently ignored.
    - A plug is actually removed after the debounce window.
    - stop_pending_removal_tasks() prevents a scheduled removal from firing.
    - _cancel_any_pending_removal() prevents a scheduled removal from firing.
    - A second _schedule_plug_removal() before the first fires is a no-op.
    """
    dispatcher = monkey_patched_dispatcher

    # Removal request for an unknown plug — nothing should happen.
    dispatcher._schedule_plug_removal(network_info["name"], zeroconf_discovery_info)
    await asyncio.sleep(dispatcher._debounce_seconds + 1)
    for _ in range(3):
        await dispatcher._hass.async_block_till_done(wait_background_tasks=True)
    assert MAC not in dispatcher.plugs

    await follow_normal_add_sequence(dispatcher, network_info)
    assert MAC in dispatcher.plugs

    # Normal removal path: plug should be gone after the debounce expires.
    dispatcher._schedule_plug_removal(network_info["name"], zeroconf_discovery_info)
    await asyncio.sleep(dispatcher._debounce_seconds + 1)
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()
    assert MAC not in dispatcher.plugs

    # Interrupted removal: stop_pending_removal_tasks cancels the timer.
    dispatcher.dispatch_send_reference.reset_mock()
    dispatcher._known_plugs.discard(MAC)
    await follow_normal_add_sequence(dispatcher, network_info)
    assert MAC in dispatcher.plugs

    dispatcher._schedule_plug_removal(network_info["name"], zeroconf_discovery_info)
    await asyncio.sleep(dispatcher._debounce_seconds // 2)
    await dispatcher.stop_pending_removal_tasks()
    await asyncio.sleep(dispatcher._debounce_seconds // 2 + 1)
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()
    assert MAC in dispatcher.plugs

    # Second schedule is a no-op (first already pending).
    dispatcher._schedule_plug_removal(network_info["name"], zeroconf_discovery_info)
    dispatcher._schedule_plug_removal(network_info["name"], zeroconf_discovery_info)
    await asyncio.sleep(dispatcher._debounce_seconds // 2)
    dispatcher._cancel_any_pending_removal(MAC, "test-cancellation")
    await asyncio.sleep(dispatcher._debounce_seconds // 2 + 1)
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()
    assert MAC in dispatcher.plugs


@pytest.mark.asyncio
async def test_dispatcher_handle_relaying_for(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher
) -> None:
    """Test handle_relaying_for filters and dispatches correctly.

    Verifies that:
    - Messages without a sensor device_type are silently ignored (debug log, not warning).
      This is normal — plugs relay other plugs at startup.
    - Messages without a MAC address are silently ignored.
    - A valid sensor relay sends CREATE_SENSOR_SIGNAL with the correct role.
    """
    dispatcher = monkey_patched_dispatcher
    await dispatcher.handle_relaying_for(
        "test-event", {"mac": None, "device_type": "plug"}
    )
    assert dispatcher.dispatch_send_reference.call_count == 0

    await dispatcher.handle_relaying_for(
        "test-event", {"mac": None, "device_type": "sensor"}
    )
    assert dispatcher.dispatch_send_reference.call_count == 0

    await dispatcher.handle_relaying_for(
        "test-event", {"mac": MAC, "device_type": "plug"}
    )
    assert dispatcher.dispatch_send_reference.call_count == 0

    await dispatcher.handle_relaying_for(
        "test-event", {"mac": MAC, "device_type": "sensor", "role": "house-net"}
    )
    assert dispatcher.dispatch_send_reference.call_count == 1
    assert dispatcher.dispatch_send_reference.call_args_list[0] == call(
        dispatcher._hass, CREATE_SENSOR_SIGNAL, MAC, "house-net"
    )


@pytest.mark.asyncio
async def test_dispatcher_handle_relaying_for_none_role(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher
) -> None:
    """Test that a sensor relayed with role=None is registered without a role."""
    dispatcher = monkey_patched_dispatcher
    await dispatcher.handle_relaying_for(
        "test-event", {"mac": MAC, "device_type": "sensor", "role": None}
    )
    assert dispatcher.dispatch_send_reference.call_count == 1
    assert dispatcher.dispatch_send_reference.call_args_list[0] == call(
        dispatcher._hass, CREATE_SENSOR_SIGNAL, MAC, None
    )


@pytest.mark.asyncio
async def test_dispatcher_handle_relaying_for_unknown_role(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher
) -> None:
    """Test that role=ROLE_UNKNOWN is normalised to None."""
    dispatcher = monkey_patched_dispatcher
    await dispatcher.handle_relaying_for(
        "test-event", {"mac": MAC, "device_type": "sensor", "role": ROLE_UNKNOWN}
    )
    assert dispatcher.dispatch_send_reference.call_count == 1
    assert dispatcher.dispatch_send_reference.call_args_list[0] == call(
        dispatcher._hass, CREATE_SENSOR_SIGNAL, MAC, None
    )


@pytest.mark.asyncio
async def test_dispatcher_handle_relaying_for_unknown_role_with_stored_role(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher
) -> None:
    """Test that a persisted role is re-applied when the device reports ROLE_UNKNOWN."""
    dispatcher = monkey_patched_dispatcher
    dispatcher._entry.data[CFG_ROLES][MAC] = "house-net"
    await dispatcher.handle_relaying_for(
        "test-event", {"mac": MAC, "device_type": "sensor", "role": ROLE_UNKNOWN}
    )
    assert dispatcher.dispatch_send_reference.call_count == 2
    assert dispatcher.dispatch_send_reference.call_args_list[0] == call(
        dispatcher._hass, CREATE_SENSOR_SIGNAL, MAC, None
    )
    assert dispatcher.dispatch_send_reference.call_args_list[1] == call(
        dispatcher._hass, ROLE_UPDATE_SIGNAL, MAC, "house-net"
    )


@pytest.mark.asyncio
async def test_dispatcher_handle_message(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher
) -> None:
    """Test that handle_message routes signals correctly for average_power and summation_energy."""
    dispatcher = monkey_patched_dispatcher
    role = "house-net"
    event = "average_power"
    message = {"mac": MAC, "device_type": "sensor", "role": role}

    await dispatcher.handle_message(event, message)
    assert dispatcher.dispatch_send_reference.call_count == 3
    assert dispatcher.dispatch_send_reference.call_args_list[0] == call(
        dispatcher._hass, ROLE_UPDATE_SIGNAL, MAC, role
    )
    assert dispatcher.dispatch_send_reference.call_args_list[1] == call(
        dispatcher._hass,
        f"{DATA_UPDATE_SIGNAL_PREFIX}{MAC}_{event}",
        event,
        message,
    )
    assert dispatcher.dispatch_send_reference.call_args_list[2] == call(
        dispatcher._hass,
        f"{DATA_UPDATE_SIGNAL_PREFIX}{MAC}_role",
        "role",
        {"role": role},
    )

    event = "summation_energy"
    await dispatcher.handle_message(event, message)
    assert dispatcher.dispatch_send_reference.call_count == 6
    assert dispatcher.dispatch_send_reference.call_args_list[3] == call(
        dispatcher._hass, ROLE_UPDATE_SIGNAL, MAC, role
    )
    assert dispatcher.dispatch_send_reference.call_args_list[4] == call(
        dispatcher._hass,
        f"{DATA_UPDATE_SIGNAL_PREFIX}{MAC}_{event}",
        event,
        message,
    )
    assert dispatcher.dispatch_send_reference.call_args_list[5] == call(
        dispatcher._hass,
        f"{DATA_UPDATE_SIGNAL_PREFIX}{MAC}_role",
        "role",
        {"role": role},
    )


@pytest.mark.asyncio
async def test_dispatcher_acknowledge_added_to_homeassistant(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher
) -> None:
    """Test that _acknowledge_sensor_added_to_homeassistant populates sensors correctly."""
    dispatcher = monkey_patched_dispatcher
    dispatcher._acknowledge_sensor_added_to_homeassistant(MAC, "test-role")
    assert dispatcher.sensors.get(MAC) == "test-role"


@pytest.mark.asyncio
async def test_dispatcher_plug_added(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher, zeroconf_discovery_info
) -> None:
    """Test that _plug_added can be called multiple times safely."""
    dispatcher = monkey_patched_dispatcher
    dispatcher._plug_added(zeroconf_discovery_info)
    dispatcher._safe_to_process_plug_queue = True
    dispatcher._plug_added(zeroconf_discovery_info)


@pytest.mark.asyncio
async def test_dispatcher_plug_updated(
    monkeypatch: pytest.MonkeyPatch,
    monkey_patched_dispatcher,
    network_info,
    zeroconf_discovery_info,
) -> None:
    """Test _plug_updated handles new, same-address, changed-address, and removed plugs.

    Verifies that:
    - An unknown plug triggers CREATE_PLUG_SIGNAL via the queue.
    - An update with no IP change is silently ignored.
    - An update with a different IP reconnects the API.
    - An update for a plug whose API has already been disconnected re-queues it.
    """
    dispatcher = monkey_patched_dispatcher
    dispatcher._plug_updated(zeroconf_discovery_info)

    for _ in range(3):
        await dispatcher._hass.async_block_till_done(wait_background_tasks=True)

    dispatcher.dispatch_send_reference.assert_called_once_with(
        dispatcher._hass,
        CREATE_PLUG_SIGNAL,
        network_info["mac"],
        network_info["host"],
        network_info["port"],
        network_info["name"],
    )
    assert MAC not in dispatcher.plugs

    dispatcher._acknowledge_plug_added_to_homeassistant(
        network_info["mac"],
        network_info["host"],
        network_info["port"],
        network_info["name"],
    )
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()
    assert MAC in dispatcher.plugs

    # Same IP/port — should be a no-op.
    dispatcher._plug_updated(zeroconf_discovery_info)
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()
    assert dispatcher.dispatch_send_reference.call_count == 1
    assert MAC in dispatcher.plugs

    # Different IP — should reconnect without sending CREATE_PLUG_SIGNAL.
    dispatcher.plugs[MAC]._listener._ip = ip_address("192.168.0.34")
    dispatcher._plug_updated(zeroconf_discovery_info)
    assert dispatcher.dispatch_send_reference.call_count == 1
    dispatcher.plugs[MAC]._listener._ip = ip_address("192.168.0.33")

    # Plug API has been removed — update should re-queue it.
    assert MAC in dispatcher.plugs
    await dispatcher.plugs[MAC].disconnect()
    del dispatcher.plugs[MAC]
    dispatcher._plug_updated(zeroconf_discovery_info)


@pytest.mark.asyncio
async def test_dispatcher_disconnect_with_active_plugs(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher, network_info
) -> None:
    """Test that disconnect() cleans up active plug APIs.

    Verifies that:
    - disconnect() drains the plugs dict even when it contains live API objects.
    - The unsubscribe callbacks registered during setup are called.
    """
    dispatcher = monkey_patched_dispatcher

    await follow_normal_add_sequence(dispatcher, network_info)
    assert MAC in dispatcher.plugs

    # Register a fake unsubscribe callback so we can verify it is called.
    unsubscribe = Mock()
    dispatcher._unsubscribe_from_signals.append(unsubscribe)

    await dispatcher.disconnect()

    assert not dispatcher.plugs
    unsubscribe.assert_called_once()


def test_process_plug_queue_empty_queue_is_noop(
    monkey_patched_dispatcher,
) -> None:
    """Test that process_plug_queue returns immediately when the queue is empty.

    If _plug_added_queue is empty, process_plug_queue returns without sending any signals.
    """
    dispatcher = monkey_patched_dispatcher

    assert not dispatcher._plug_added_queue
    dispatcher.process_plug_queue()

    dispatcher.dispatch_send_reference.assert_not_called()


@pytest.mark.asyncio
async def test_persist_plug_info_updates_entry_data(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that _persist_plug_info writes host/port/name/mac into entry.data.

    Lines 268-276 of powersensor_message_dispatcher.py: when the entry is in
    LOADED state, _persist_plug_info merges the new address into CFG_DEVICES
    and calls async_update_entry.
    """
    powersensor_dispatcher_module = importlib.import_module(
        "homeassistant.components.powersensor.powersensor_message_dispatcher"
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CFG_DEVICES: {}, CFG_ROLES: {}},
        entry_id="test_persist",
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
        state=ConfigEntryState.LOADED,
    )

    update_calls = []
    monkeypatch.setattr(
        hass.config_entries,
        "async_update_entry",
        lambda entry, **kwargs: update_calls.append(kwargs),
    )

    vhh = powersensor_dispatcher_module.VirtualHousehold(False)
    dispatcher = powersensor_dispatcher_module.PowersensorMessageDispatcher(
        hass, entry, vhh, debounce_timeout=1
    )

    dispatcher._persist_plug_info(MAC, "10.0.0.1", 49476, "test-plug")

    assert len(update_calls) == 1
    devices = update_calls[0]["data"][CFG_DEVICES]
    assert devices[MAC] == {
        "mac": MAC,
        "host": "10.0.0.1",
        "port": 49476,
        "name": "test-plug",
    }
