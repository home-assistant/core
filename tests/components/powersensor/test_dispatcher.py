"""Tests related to Powersensor's Home Assistant integration's message dispatcher."""

import asyncio
import importlib
from ipaddress import ip_address
import logging
from unittest.mock import Mock, call

import pytest

from homeassistant.components.powersensor.const import (
    CREATE_PLUG_SIGNAL,
    CREATE_SENSOR_SIGNAL,
    DATA_UPDATE_SIGNAL_FMT_MAC_EVENT,
    ROLE_UPDATE_SIGNAL,
)
from homeassistant.core import HomeAssistant

MAC = "a4cf1218f158"


logging.getLogger().setLevel(logging.CRITICAL)


@pytest.fixture
def monkey_patched_dispatcher(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch):
    """Return a PowersensorMessageDispatcher instance with its dependencies monkey-patched.

    This fixture sets up a dispatcher with a mock dispatcher connect and send function,
    as well as a mock virtual household. The `async_create_background_task` function on
    the Home Assistant instance is also patched to create tasks synchronously.
    """

    def create_task(coroutine, name=None):
        return asyncio.create_task(coroutine)

    monkeypatch.setattr(hass, "async_create_background_task", create_task)

    powersensor_dispatcher_module = importlib.import_module(
        "homeassistant.components.powersensor.PowersensorMessageDispatcher"
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
    dispatcher = powersensor_dispatcher_module.PowersensorMessageDispatcher(
        hass, entry, vhh, debounce_timeout=2
    )
    if not hasattr(dispatcher, "dispatch_send_reference"):
        object.__setattr__(dispatcher, "dispatch_send_reference", {})
    dispatcher.dispatch_send_reference = async_dispatcher_send

    return dispatcher


@pytest.fixture
def network_info():
    """Return network information for the Powersensor gateway.

    This fixture provides a dictionary containing the MAC address, IP address,
    port number, and name of the Powersensor gateway.
    """
    return {
        "mac": MAC,
        "host": ip_address("192.168.0.33"),
        "port": 49476,
        "name": f"Powersensor-gateway-{MAC}-civet._powersensor._udp.local.",
    }


@pytest.fixture
def zeroconf_discovery_info():
    """Return discovery information for the Powersensor gateway via Zeroconf.

    This fixture provides a dictionary containing information about the Powersensor
    gateway, including its type, name, addresses, port number, and properties.
    """
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
    """Simulate adding a plug to Home Assistant via the normal add sequence.

    This function exercises the `enqueue_plug_for_adding`, `process_plug_queue`,
    and `_acknowledge_plug_added_to_homeassistant` methods of the dispatcher.
    It verifies that:
    - The correct signal is sent when adding a plug.
    - An API object is created for the added plug.
    """
    assert not dispatcher.plugs
    await dispatcher.enqueue_plug_for_adding(network_info)
    await dispatcher.process_plug_queue()
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()

    # check signal was sent to sensors
    dispatcher.dispatch_send_reference.assert_called_once_with(
        dispatcher._hass,
        CREATE_PLUG_SIGNAL,
        network_info["mac"],
        network_info["host"],
        network_info["port"],
        network_info["name"],
    )

    # if we're at this point the signal should be coming back triggering acknowledge
    await dispatcher._acknowledge_plug_added_to_homeassistant(
        network_info["mac"],
        network_info["host"],
        network_info["port"],
        network_info["name"],
    )
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()

    # an api object should have been created
    assert MAC in dispatcher.plugs
    # Think this is a sign that the finally block is not running as expected.
    # @todo: delete this block here as well after investigation complete
    if dispatcher._monitor_add_plug_queue is not None:
        dispatcher._monitor_add_plug_queue.cancel()
        try:
            await dispatcher._monitor_add_plug_queue
        except asyncio.CancelledError:
            pass
        finally:
            dispatcher._monitor_add_plug_queue = None


@pytest.mark.asyncio
async def test_dispatcher_monitor_plug_queue(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher, network_info
) -> None:
    """Test the `enqueue_plug_for_adding` and `process_plug_queue` methods of the dispatcher.

    This test verifies that:
    - The correct API object is created when adding a plug.
    - The queue is properly cleared after adding a plug.
    """
    dispatcher = monkey_patched_dispatcher

    # mac address known, but not in plugs
    dispatcher._known_plugs.add(MAC)

    assert not dispatcher.plugs
    await dispatcher.enqueue_plug_for_adding(network_info)
    await dispatcher.process_plug_queue()
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()

    # an api object should have been created
    assert MAC in dispatcher.plugs
    # Think this is a sign that the finally block is not running as expected.
    # @todo: investigate dispatcher plug queue watching task cleanup
    if dispatcher._monitor_add_plug_queue is not None:
        dispatcher._monitor_add_plug_queue.cancel()
        try:
            await dispatcher._monitor_add_plug_queue
        except asyncio.CancelledError:
            pass
        finally:
            dispatcher._monitor_add_plug_queue = None

    for _ in range(3):
        await dispatcher._hass.async_block_till_done()
    # try to see if queue gets properly cleared
    await dispatcher.enqueue_plug_for_adding(network_info)
    await dispatcher.process_plug_queue()
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()

    assert MAC in dispatcher.plugs


@pytest.mark.asyncio
async def test_dispatcher_monitor_plug_queue_error_handling(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher, network_info
) -> None:
    """Test error handling when adding a plug to Home Assistant.

    This test verifies that:
    - An error does not create an API object in the plugs dictionary.
    """
    dispatcher = monkey_patched_dispatcher

    def raise_error(*args, **kwargs):
        raise NotImplementedError

    monkeypatch.setattr(dispatcher, "_plug_has_been_seen", raise_error)
    assert not dispatcher.plugs
    await dispatcher.enqueue_plug_for_adding(network_info)
    await dispatcher.process_plug_queue()
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()
    assert not dispatcher.plugs


@pytest.mark.asyncio
async def test_dispatcher_handle_plug_exception(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher, network_info
) -> None:
    """Test handling of plug exceptions by the dispatcher.

    This test verifies that:
    - The `handle_exception` method does not crash when passed an exception.
    """
    # for now, I pointlessly verify this does not crash
    powersensor_dispatcher_module = importlib.import_module(
        "homeassistant.components.powersensor.PowersensorMessageDispatcher"
    )
    await powersensor_dispatcher_module.handle_exception(
        "exception", NotImplementedError
    )


@pytest.mark.asyncio
async def test_dispatcher_removal(
    monkeypatch: pytest.MonkeyPatch,
    monkey_patched_dispatcher,
    network_info,
    zeroconf_discovery_info,
) -> None:
    """Test removal of plugs from Home Assistant via the dispatcher.

    This test verifies that:
    - A plug can be removed when not yet added.
    - A plug can be removed after being added.
    - Pending removal tasks can be cancelled and removed.
    - Interrupting a pending removal task prevents it from completing.
    """
    dispatcher = monkey_patched_dispatcher

    # test removal of plug not added
    await dispatcher._schedule_plug_removal(
        network_info["name"], zeroconf_discovery_info
    )
    await asyncio.sleep(dispatcher._debounce_seconds + 1)
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()

    assert MAC not in dispatcher.plugs

    await follow_normal_add_sequence(dispatcher, network_info)

    await dispatcher._schedule_plug_removal(
        network_info["name"], zeroconf_discovery_info
    )
    await asyncio.sleep(dispatcher._debounce_seconds + 1)
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()
    assert MAC not in dispatcher.plugs

    await follow_normal_add_sequence(dispatcher, network_info)
    assert MAC in dispatcher.plugs
    await dispatcher._schedule_plug_removal(
        network_info["name"], zeroconf_discovery_info
    )

    await asyncio.sleep(dispatcher._debounce_seconds // 2)
    await dispatcher.stop_pending_removal_tasks()
    await asyncio.sleep(dispatcher._debounce_seconds // 2 + 1)
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()
    # the removal should not have happened if it was interrupted
    assert MAC in dispatcher.plugs

    # cancel just one mac
    await dispatcher._schedule_plug_removal(
        network_info["name"], zeroconf_discovery_info
    )
    await dispatcher._schedule_plug_removal(
        network_info["name"], zeroconf_discovery_info
    )
    await asyncio.sleep(dispatcher._debounce_seconds // 2)
    await dispatcher.cancel_any_pending_removal(MAC, "test-cancellation")
    await asyncio.sleep(dispatcher._debounce_seconds // 2 + 1)
    for _ in range(3):
        await dispatcher._hass.async_block_till_done()
    # the removal should not have happened if it was interrupted
    assert MAC in dispatcher.plugs


@pytest.mark.asyncio
async def test_dispatcher_handle_relaying_for(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher
) -> None:
    """Test handling of relay events by the dispatcher.

    This test verifies that:
    - Relay events are ignored when no device type or mac is specified.
    - Relay events trigger dispatches with the correct signal and arguments.
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
    assert dispatcher.dispatch_send_reference.call_count == 2
    dispatcher.dispatch_send_reference.call_args_list[0] = call(
        dispatcher._hass, CREATE_SENSOR_SIGNAL, MAC, "house-net"
    )
    dispatcher.dispatch_send_reference.call_args_list[1] = call(
        dispatcher._hass, ROLE_UPDATE_SIGNAL, MAC, "house-net"
    )


@pytest.mark.asyncio
async def test_dispatcher_handle_message(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher
) -> None:
    """Test handling of messages by the dispatcher.

    This test verifies that:
    - The `handle_message` method sends the correct signals when receiving sensor data.
    """
    dispatcher = monkey_patched_dispatcher
    role = "house-net"
    event = "average_power"
    message = {"mac": MAC, "device_type": "sensor", "role": role}
    await dispatcher.handle_message(event, message)
    assert dispatcher.dispatch_send_reference.call_count == 3
    dispatcher.dispatch_send_reference.call_args_list[0] = call(
        dispatcher._hass, ROLE_UPDATE_SIGNAL, MAC, role
    )
    dispatcher.dispatch_send_reference.call_args_list[1] = call(
        dispatcher._hass,
        DATA_UPDATE_SIGNAL_FMT_MAC_EVENT % (MAC, event),
        event,
        message,
    )
    dispatcher.dispatch_send_reference.call_args_list[2] = call(
        dispatcher._hass,
        DATA_UPDATE_SIGNAL_FMT_MAC_EVENT % (MAC, "role"),
        "role",
        {"role": role},
    )
    event = "summation_energy"
    await dispatcher.handle_message(event, message)
    assert dispatcher.dispatch_send_reference.call_count == 6
    dispatcher.dispatch_send_reference.call_args_list[3] = call(
        dispatcher._hass, ROLE_UPDATE_SIGNAL, MAC, role
    )
    dispatcher.dispatch_send_reference.call_args_list[4] = call(
        dispatcher._hass,
        DATA_UPDATE_SIGNAL_FMT_MAC_EVENT % (MAC, event),
        event,
        message,
    )
    dispatcher.dispatch_send_reference.call_args_list[5] = call(
        dispatcher._hass,
        DATA_UPDATE_SIGNAL_FMT_MAC_EVENT % (MAC, "role"),
        "role",
        {"role": role},
    )


@pytest.mark.asyncio
async def test_dispatcher_acknowledge_added_to_homeassistant(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher
) -> None:
    """Test acknowledgement of sensors added to Home Assistant by the dispatcher.

    This test verifies that:
    - The `sensors` dictionary is updated correctly when acknowledging a sensor.
    """
    dispatcher = monkey_patched_dispatcher
    dispatcher._acknowledge_sensor_added_to_homeassistant(MAC, "test-role")
    assert dispatcher.sensors.get(MAC, None) == "test-role"


@pytest.mark.asyncio
async def test_dispatcher_plug_added(
    monkeypatch: pytest.MonkeyPatch, monkey_patched_dispatcher, zeroconf_discovery_info
) -> None:
    """Test adding of plugs by the dispatcher.

    This test verifies that:
    - The `_plug_added` method can be called multiple times when safe.
    """
    dispatcher = monkey_patched_dispatcher
    await dispatcher._plug_added(zeroconf_discovery_info)
    dispatcher._safe_to_process_plug_queue = True
    await dispatcher._plug_added(zeroconf_discovery_info)


@pytest.mark.asyncio
async def test_dispatcher_plug_updated(
    monkeypatch: pytest.MonkeyPatch,
    monkey_patched_dispatcher,
    network_info,
    zeroconf_discovery_info,
) -> None:
    """Test updating of plugs by the dispatcher.

    This test verifies that:
    - The `_plug_updated` method sends the correct signal when a plug is updated.
    - Plug updates are handled correctly even if the IP address or device has changed.
    - Plug removals do not trigger an update.
    """
    dispatcher = monkey_patched_dispatcher
    await dispatcher._plug_updated(zeroconf_discovery_info)

    for _ in range(3):
        await dispatcher._hass.async_block_till_done()

    dispatcher.dispatch_send_reference.assert_called_once_with(
        dispatcher._hass,
        CREATE_PLUG_SIGNAL,
        network_info["mac"],
        network_info["host"],
        network_info["port"],
        network_info["name"],
    )
    assert MAC not in dispatcher.plugs
    await follow_normal_add_sequence(dispatcher, network_info)
    assert MAC in dispatcher.plugs

    await dispatcher._plug_updated(zeroconf_discovery_info)

    for _ in range(3):
        await dispatcher._hass.async_block_till_done()

    assert dispatcher.dispatch_send_reference.call_count == 1
    assert MAC in dispatcher.plugs
    # fake ip mismatch
    dispatcher.plugs[MAC]._listener._ip = ip_address("192.168.0.34")
    await dispatcher._plug_updated(zeroconf_discovery_info)
    assert dispatcher.dispatch_send_reference.call_count == 1
    dispatcher.plugs[MAC]._listener._ip = ip_address("192.168.0.33")
    # fake plug removal
    assert MAC in dispatcher.plugs
    await dispatcher.plugs[MAC].disconnect()
    del dispatcher.plugs[MAC]
    await dispatcher._plug_updated(zeroconf_discovery_info)
