"""Tests for PowersensorMessageDispatcher — the new event-router design.

The refactored dispatcher no longer owns plug connections, a zeroconf queue,
or debounce timers.  Its sole responsibility is translating the unified
PowersensorDevices event stream into HA dispatcher signals and tracking which
MACs have been seen so that rescans don't create duplicate entities.

All tests drive the dispatcher through its single public entry point:
on_device_event().
"""

import importlib
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from homeassistant.components.powersensor_au.const import (
    CFG_ROLES,
    CREATE_PLUG_SIGNAL,
    CREATE_SENSOR_SIGNAL,
    DATA_UPDATE_SIGNAL_PREFIX,
    ROLE_UNKNOWN,
    ROLE_UPDATE_SIGNAL,
)
from homeassistant.core import HomeAssistant

MAC = "a4cf1218f158"
OTHER_MAC = "a4cf1218f159"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dispatcher_module():
    """Return the dispatcher module so monkeypatches are scoped to it."""
    return importlib.import_module(
        "homeassistant.components.powersensor_au.powersensor_message_dispatcher"
    )


@pytest.fixture
def mock_devices():
    """Return a minimal mock for PowersensorDevices."""
    devices = MagicMock()
    devices.subscribe = Mock()
    devices.unsubscribe = Mock()
    return devices


@pytest.fixture
def patched_dispatcher(
    hass: HomeAssistant,
    dispatcher_module,
    monkeypatch: pytest.MonkeyPatch,
    mock_devices,
):
    """Return a PowersensorMessageDispatcher with async_dispatcher_send patched.

    The entry mock is pre-populated with empty roles and a devices attribute so
    that subscribe() calls inside _handle_device_found succeed without
    touching the network.
    """
    send = Mock()
    monkeypatch.setattr(dispatcher_module, "async_dispatcher_send", send)

    vhh = dispatcher_module.VirtualHousehold(False)

    entry = Mock()
    entry.data = {CFG_ROLES: {}}
    # Provide runtime_data.devices so _handle_device_found can call subscribe().
    entry.runtime_data = Mock()
    entry.runtime_data.devices = mock_devices

    dispatcher = dispatcher_module.PowersensorMessageDispatcher(hass, entry, vhh)
    dispatcher._send = send  # convenience reference for assertions
    return dispatcher


# ---------------------------------------------------------------------------
# device_found — plug
# ---------------------------------------------------------------------------


async def test_device_found_plug_sends_create_plug_signal(
    patched_dispatcher,
) -> None:
    """A device_found event for a plug sends CREATE_PLUG_SIGNAL exactly once."""
    d = patched_dispatcher

    await d.on_device_event(
        {"event": "device_found", "mac": MAC, "device_type": "plug"}
    )

    d._send.assert_called_once_with(d._hass, CREATE_PLUG_SIGNAL, MAC)
    assert MAC in d.plugs


async def test_device_found_plug_deduplicates_on_rescan(
    patched_dispatcher,
) -> None:
    """A second device_found for the same plug MAC is silently ignored."""
    d = patched_dispatcher

    await d.on_device_event(
        {"event": "device_found", "mac": MAC, "device_type": "plug"}
    )
    await d.on_device_event(
        {"event": "device_found", "mac": MAC, "device_type": "plug"}
    )

    d._send.assert_called_once_with(d._hass, CREATE_PLUG_SIGNAL, MAC)


async def test_device_found_plug_missing_mac_is_ignored(
    patched_dispatcher,
) -> None:
    """A device_found event with no MAC is silently dropped."""
    d = patched_dispatcher

    await d.on_device_event({"event": "device_found", "device_type": "plug"})

    d._send.assert_not_called()


async def test_device_found_plug_calls_subscribe(
    patched_dispatcher, mock_devices
) -> None:
    """subscribe() is called on the devices layer when a new plug is found."""
    d = patched_dispatcher

    await d.on_device_event(
        {"event": "device_found", "mac": MAC, "device_type": "plug"}
    )

    mock_devices.subscribe.assert_called_once_with(MAC)


# ---------------------------------------------------------------------------
# device_found — sensor
# ---------------------------------------------------------------------------


async def test_device_found_sensor_sends_create_sensor_signal(
    patched_dispatcher,
) -> None:
    """A device_found event for a sensor sends CREATE_SENSOR_SIGNAL with its role."""
    d = patched_dispatcher

    await d.on_device_event(
        {
            "event": "device_found",
            "mac": MAC,
            "device_type": "sensor",
            "role": "house-net",
        }
    )

    d._send.assert_called_once_with(d._hass, CREATE_SENSOR_SIGNAL, MAC, "house-net")
    assert MAC in d.sensors
    assert d.sensors[MAC] == "house-net"


async def test_device_found_sensor_role_unknown_normalised_to_none(
    patched_dispatcher,
) -> None:
    """ROLE_UNKNOWN from the library is normalised to None before signalling."""
    d = patched_dispatcher

    await d.on_device_event(
        {
            "event": "device_found",
            "mac": MAC,
            "device_type": "sensor",
            "role": ROLE_UNKNOWN,
        }
    )

    d._send.assert_called_once_with(d._hass, CREATE_SENSOR_SIGNAL, MAC, None)


async def test_device_found_sensor_falls_back_to_persisted_role(
    patched_dispatcher,
) -> None:
    """When the library omits the role, the persisted role from entry.data is used."""
    d = patched_dispatcher
    d._entry.data = {CFG_ROLES: {MAC: "solar"}}

    await d.on_device_event(
        {"event": "device_found", "mac": MAC, "device_type": "sensor"}
    )

    d._send.assert_called_once_with(d._hass, CREATE_SENSOR_SIGNAL, MAC, "solar")


async def test_device_found_sensor_deduplicates_on_rescan(
    patched_dispatcher,
) -> None:
    """A second device_found for the same sensor MAC is silently ignored."""
    d = patched_dispatcher

    await d.on_device_event(
        {
            "event": "device_found",
            "mac": MAC,
            "device_type": "sensor",
            "role": "house-net",
        }
    )
    await d.on_device_event(
        {
            "event": "device_found",
            "mac": MAC,
            "device_type": "sensor",
            "role": "house-net",
        }
    )

    d._send.assert_called_once()


async def test_device_found_sensor_calls_subscribe(
    patched_dispatcher, mock_devices
) -> None:
    """subscribe() is called on the devices layer when a new sensor is found."""
    d = patched_dispatcher

    await d.on_device_event(
        {
            "event": "device_found",
            "mac": MAC,
            "device_type": "sensor",
            "role": "house-net",
        }
    )

    mock_devices.subscribe.assert_called_once_with(MAC)


# ---------------------------------------------------------------------------
# device_lost
# ---------------------------------------------------------------------------


async def test_device_lost_is_logged_and_does_not_remove_entities(
    patched_dispatcher,
) -> None:
    """device_lost is handled without sending any HA signals.

    The library manages reconnection; entities become unavailable via their own
    timeout rather than being removed.
    """
    d = patched_dispatcher
    d.plugs.add(MAC)

    await d.on_device_event({"event": "device_lost", "mac": MAC})

    d._send.assert_not_called()
    # The plug must remain in d.plugs — removal is not triggered.
    assert MAC in d.plugs


async def test_device_lost_missing_mac_is_ignored(patched_dispatcher) -> None:
    """A device_lost event with no MAC field does not raise."""
    d = patched_dispatcher

    await d.on_device_event({"event": "device_lost"})

    d._send.assert_not_called()


# ---------------------------------------------------------------------------
# scan_complete
# ---------------------------------------------------------------------------


async def test_scan_complete_sends_no_signals(patched_dispatcher) -> None:
    """scan_complete is consumed silently without any HA dispatcher signals."""
    d = patched_dispatcher

    await d.on_device_event({"event": "scan_complete", "gateway_count": 2})

    d._send.assert_not_called()


# ---------------------------------------------------------------------------
# Unknown / missing event type
# ---------------------------------------------------------------------------


async def test_event_with_no_event_key_is_ignored(patched_dispatcher) -> None:
    """An event dict missing the 'event' key is silently dropped.

    The match statement's wildcard branch only calls _handle_measurement when
    event_type is not None.  A missing key produces None and must be a no-op.
    """
    d = patched_dispatcher

    await d.on_device_event({"mac": MAC, "watts": 100})

    d._send.assert_not_called()


async def test_event_with_none_event_type_is_ignored(patched_dispatcher) -> None:
    """An event dict with event=None is silently dropped."""
    d = patched_dispatcher

    await d.on_device_event({"event": None, "mac": MAC})

    d._send.assert_not_called()


# ---------------------------------------------------------------------------
# Measurement events
# ---------------------------------------------------------------------------


async def test_measurement_with_no_mac_is_ignored(patched_dispatcher) -> None:
    """A measurement event with no 'mac' key is silently dropped (line 175).

    _handle_measurement guards mac is None immediately after extracting it;
    this exercises that early return path.
    """
    d = patched_dispatcher

    # An average_power event with no mac must not send any signals.
    await d.on_device_event({"event": "average_power", "watts": 500})

    d._send.assert_not_called()


async def test_measurement_routes_data_update_signal(patched_dispatcher) -> None:
    """A measurement event is routed to DATA_UPDATE_SIGNAL_PREFIX + mac + event."""
    d = patched_dispatcher
    d.sensors[MAC] = "house-net"
    d._entry.data = {CFG_ROLES: {MAC: "house-net"}}

    message = {"mac": MAC, "role": "house-net", "watts": 500}
    await d.on_device_event({**message, "event": "average_power"})

    signal_calls = [call.args[1] for call in d._send.call_args_list]
    assert f"{DATA_UPDATE_SIGNAL_PREFIX}{MAC}_average_power" in signal_calls
    assert f"{DATA_UPDATE_SIGNAL_PREFIX}{MAC}_role" in signal_calls


async def test_measurement_sends_role_update_signal_when_role_changes(
    patched_dispatcher,
) -> None:
    """A measurement whose role differs from the persisted one fires ROLE_UPDATE_SIGNAL."""
    d = patched_dispatcher
    d.sensors[MAC] = None
    d._entry.data = {CFG_ROLES: {}}

    message = {"mac": MAC, "role": "house-net", "watts": 100}
    await d.on_device_event({**message, "event": "average_power"})

    signal_names = [call.args[1] for call in d._send.call_args_list]
    assert ROLE_UPDATE_SIGNAL in signal_names


async def test_measurement_does_not_send_role_update_when_role_matches(
    patched_dispatcher,
) -> None:
    """No ROLE_UPDATE_SIGNAL when the reported role already matches stored state."""
    d = patched_dispatcher
    d.sensors[MAC] = "house-net"
    d._entry.data = {CFG_ROLES: {MAC: "house-net"}}

    message = {"mac": MAC, "role": "house-net", "watts": 100}
    await d.on_device_event({**message, "event": "average_power"})

    signal_names = [call.args[1] for call in d._send.call_args_list]
    assert ROLE_UPDATE_SIGNAL not in signal_names


async def test_measurement_for_unknown_mac_creates_sensor(
    patched_dispatcher,
) -> None:
    """A measurement from a MAC not yet in sensors or plugs triggers CREATE_SENSOR_SIGNAL.

    This is the late-discovery path: a sensor that relayed data before its
    device_found event was processed.
    """
    d = patched_dispatcher
    assert MAC not in d.sensors
    assert MAC not in d.plugs

    message = {"mac": MAC, "role": "house-net", "watts": 200}
    await d.on_device_event({**message, "event": "average_power"})

    signal_names = [call.args[1] for call in d._send.call_args_list]
    assert CREATE_SENSOR_SIGNAL in signal_names


async def test_measurement_average_power_feeds_vhh(
    hass: HomeAssistant,
    dispatcher_module,
    monkeypatch: pytest.MonkeyPatch,
    mock_devices,
) -> None:
    """average_power events are forwarded to VirtualHousehold.process_average_power_event."""
    monkeypatch.setattr(dispatcher_module, "async_dispatcher_send", Mock())

    vhh = Mock()
    vhh.process_average_power_event = AsyncMock()
    vhh.process_summation_event = AsyncMock()

    entry = Mock()
    entry.data = {CFG_ROLES: {MAC: "house-net"}}
    entry.runtime_data = Mock()
    entry.runtime_data.devices = mock_devices

    d = dispatcher_module.PowersensorMessageDispatcher(hass, entry, vhh)
    d.sensors[MAC] = "house-net"

    message = {"mac": MAC, "role": "house-net", "watts": 300}
    await d.on_device_event({**message, "event": "average_power"})

    vhh.process_average_power_event.assert_awaited_once()
    vhh.process_summation_event.assert_not_called()


async def test_measurement_summation_energy_feeds_vhh(
    hass: HomeAssistant,
    dispatcher_module,
    monkeypatch: pytest.MonkeyPatch,
    mock_devices,
) -> None:
    """summation_energy events are forwarded to VirtualHousehold.process_summation_event."""
    monkeypatch.setattr(dispatcher_module, "async_dispatcher_send", Mock())

    vhh = Mock()
    vhh.process_average_power_event = AsyncMock()
    vhh.process_summation_event = AsyncMock()

    entry = Mock()
    entry.data = {CFG_ROLES: {MAC: "house-net"}}
    entry.runtime_data = Mock()
    entry.runtime_data.devices = mock_devices

    d = dispatcher_module.PowersensorMessageDispatcher(hass, entry, vhh)
    d.sensors[MAC] = "house-net"

    message = {"mac": MAC, "role": "house-net", "summation_joules": 12345}
    await d.on_device_event({**message, "event": "summation_energy"})

    vhh.process_summation_event.assert_awaited_once()
    vhh.process_average_power_event.assert_not_called()


async def test_measurement_other_event_type_does_not_feed_vhh(
    hass: HomeAssistant,
    dispatcher_module,
    monkeypatch: pytest.MonkeyPatch,
    mock_devices,
) -> None:
    """battery_level and similar events must not call either VHH method."""
    monkeypatch.setattr(dispatcher_module, "async_dispatcher_send", Mock())

    vhh = Mock()
    vhh.process_average_power_event = AsyncMock()
    vhh.process_summation_event = AsyncMock()

    entry = Mock()
    entry.data = {CFG_ROLES: {MAC: "house-net"}}
    entry.runtime_data = Mock()
    entry.runtime_data.devices = mock_devices

    d = dispatcher_module.PowersensorMessageDispatcher(hass, entry, vhh)
    d.sensors[MAC] = "house-net"

    message = {"mac": MAC, "role": "house-net", "battery_volts": 3.8}
    await d.on_device_event({**message, "event": "battery_level"})

    vhh.process_average_power_event.assert_not_called()
    vhh.process_summation_event.assert_not_called()


# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------


async def test_disconnect_unsubscribes_all_known_devices(
    patched_dispatcher, mock_devices
) -> None:
    """disconnect() calls unsubscribe for every known plug and sensor."""
    d = patched_dispatcher
    d.plugs.add(MAC)
    d.sensors[OTHER_MAC] = "house-net"

    await d.disconnect()

    unsubscribed = {call.args[0] for call in mock_devices.unsubscribe.call_args_list}
    assert MAC in unsubscribed
    assert OTHER_MAC in unsubscribed


async def test_disconnect_with_no_devices_is_noop(patched_dispatcher) -> None:
    """disconnect() on an empty dispatcher does not raise."""
    d = patched_dispatcher
    assert not d.plugs
    assert not d.sensors

    await d.disconnect()  # must not raise
