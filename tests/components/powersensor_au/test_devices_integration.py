"""Integration tests wiring PowersensorDevices → PowersensorMessageDispatcher → HA signals.

These tests construct a real PowersensorMessageDispatcher (not a mock) and drive
it with event payloads that exactly match what the library emits.  This gives
confidence that:

  1. The dispatcher correctly interprets the library's event contract.
  2. The 'device_type:' trailing-colon quirk is handled end-to-end.
  3. Deduplication across a simulated rescan sequence works correctly.
  4. The VHH calculation layer receives the right calls from measurement events.
  5. disconnect() cleans up after a full plug + sensor lifecycle.

No real network sockets are opened.  PowersensorDevices is never instantiated;
instead the registered callback (on_device_event) is invoked directly with the
payloads that the library would produce.
"""

import importlib
from unittest.mock import AsyncMock, MagicMock, Mock

from powersensor_local import VirtualHousehold
import pytest

from homeassistant.components.powersensor_au.const import (
    CFG_ROLES,
    CREATE_PLUG_SIGNAL,
    CREATE_SENSOR_SIGNAL,
    DATA_UPDATE_SIGNAL_PREFIX,
    ROLE_UPDATE_SIGNAL,
)
from homeassistant.core import HomeAssistant

PLUG_MAC = "aabbccddeeff"
SENSOR_MAC = "112233445566"
SOLAR_MAC = "665544332211"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dispatcher_module():
    """Return the dispatcher module for scoped monkeypatching."""
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
def integration(
    hass: HomeAssistant,
    dispatcher_module,
    monkeypatch: pytest.MonkeyPatch,
    mock_devices,
):
    """Return a (dispatcher, send_mock, entry_mock) triple.

    The dispatcher is a real PowersensorMessageDispatcher with
    async_dispatcher_send patched out so we can assert on signal calls
    without needing a full HA platform setup.
    """
    send = Mock()
    monkeypatch.setattr(dispatcher_module, "async_dispatcher_send", send)

    vhh = VirtualHousehold(False)
    # Patch VHH methods so we can assert on them without a real calculation loop.
    monkeypatch.setattr(vhh, "process_average_power_event", AsyncMock())
    monkeypatch.setattr(vhh, "process_summation_event", AsyncMock())

    entry = Mock()
    entry.data = {CFG_ROLES: {}}
    entry.runtime_data = Mock()
    entry.runtime_data.devices = mock_devices

    dispatcher = dispatcher_module.PowersensorMessageDispatcher(hass, entry, vhh)

    return dispatcher, send, entry, vhh


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _signals_sent(send_mock) -> list[str]:
    """Return the list of signal names from all send() calls in order."""
    return [c.args[1] for c in send_mock.call_args_list]


def _plug_found(mac: str) -> dict[str, object]:
    """Return a device_found payload for a plug, exactly as the library emits it."""
    return {"event": "device_found", "mac": mac, "device_type:": "plug"}


def _sensor_found(mac: str, role: str | None = None) -> dict[str, str]:
    """Return a device_found payload for a sensor, exactly as the library emits it."""
    ev: dict[str, str] = {"event": "device_found", "mac": mac, "device_type:": "sensor"}
    if role is not None:
        ev["role"] = role
    return ev


def _scan_complete(gateway_count: int = 1) -> dict[str, object]:
    return {"event": "scan_complete", "gateway_count": gateway_count}


def _average_power(mac: str, role: str, watts: float) -> dict[str, object]:
    return {"event": "average_power", "mac": mac, "role": role, "watts": watts}


def _summation(mac: str, role: str, joules: int) -> dict[str, object]:
    return {
        "event": "summation_energy",
        "mac": mac,
        "role": role,
        "summation_joules": joules,
    }


def _device_lost(mac: str) -> dict[str, object]:
    return {"event": "device_lost", "mac": mac}


# ---------------------------------------------------------------------------
# Full discovery sequence
# ---------------------------------------------------------------------------


async def test_full_discovery_sequence(integration) -> None:
    """Simulate: plug found → sensor found → scan_complete → rescan finds same devices.

    Asserts:
    - CREATE_PLUG_SIGNAL and CREATE_SENSOR_SIGNAL sent once each at first discovery.
    - scan_complete generates no signals.
    - A rescan that re-emits device_found for the same MACs generates no duplicates.
    - subscribe() is called once per unique MAC.
    """
    d, send, _entry, _vhh = integration

    # First scan.
    await d.on_device_event(_plug_found(PLUG_MAC))
    await d.on_device_event(_sensor_found(SENSOR_MAC, role="house-net"))
    await d.on_device_event(_scan_complete(gateway_count=1))

    signals = _signals_sent(send)
    assert signals.count(CREATE_PLUG_SIGNAL) == 1
    assert signals.count(CREATE_SENSOR_SIGNAL) == 1

    send.reset_mock()

    # Rescan — same devices re-announced.
    await d.on_device_event(_plug_found(PLUG_MAC))
    await d.on_device_event(_sensor_found(SENSOR_MAC, role="house-net"))
    await d.on_device_event(_scan_complete(gateway_count=1))

    rescan_signals = _signals_sent(send)
    assert CREATE_PLUG_SIGNAL not in rescan_signals, (
        "Plug must not be re-created on rescan"
    )
    assert CREATE_SENSOR_SIGNAL not in rescan_signals, (
        "Sensor must not be re-created on rescan"
    )

    # subscribe() is called once on first discovery and again on each rescan
    # re-announce (sleep/wake re-subscribe logic), so after one rescan each
    # MAC has been subscribed exactly twice.
    subscribed_macs = [
        c.args[0] for c in d._entry.runtime_data.devices.subscribe.call_args_list
    ]
    assert subscribed_macs.count(PLUG_MAC) == 2, (
        "Plug must be subscribed on first discovery AND re-subscribed on rescan"
    )
    assert subscribed_macs.count(SENSOR_MAC) == 2, (
        "Sensor must be subscribed on first discovery AND re-subscribed on rescan"
    )


async def test_new_device_on_rescan_is_announced(integration) -> None:
    """A device that appears for the first time on a rescan is correctly announced."""
    d, send, _entry, _vhh = integration

    await d.on_device_event(_plug_found(PLUG_MAC))
    await d.on_device_event(_scan_complete())
    send.reset_mock()

    # A previously unseen plug appears on the rescan.
    NEW_MAC = "ffeeddccbbaa"
    await d.on_device_event(_plug_found(NEW_MAC))
    await d.on_device_event(_scan_complete())

    signals = _signals_sent(send)
    assert CREATE_PLUG_SIGNAL in signals
    plug_signal_args = [
        c.args[2] for c in send.call_args_list if c.args[1] == CREATE_PLUG_SIGNAL
    ]
    assert NEW_MAC in plug_signal_args
    assert PLUG_MAC not in plug_signal_args


# ---------------------------------------------------------------------------
# device_type: trailing-colon contract
# ---------------------------------------------------------------------------


async def test_library_event_format_plug_is_handled(integration) -> None:
    """Confirm the exact dict the library emits for a plug is handled correctly.

    This is the end-to-end colon test — it uses _plug_found() which mirrors
    the literal output of PowersensorDevices._add_device() for a plug.
    """
    d, send, _entry, _vhh = integration

    await d.on_device_event(_plug_found(PLUG_MAC))

    assert _signals_sent(send) == [CREATE_PLUG_SIGNAL]
    assert PLUG_MAC in d.plugs


async def test_library_event_format_sensor_is_handled(integration) -> None:
    """Confirm the exact dict the library emits for a sensor is handled correctly."""
    d, send, _entry, _vhh = integration

    await d.on_device_event(_sensor_found(SENSOR_MAC, role="solar"))

    signals = _signals_sent(send)
    assert CREATE_SENSOR_SIGNAL in signals
    assert SENSOR_MAC in d.sensors


# ---------------------------------------------------------------------------
# Measurement routing
# ---------------------------------------------------------------------------


async def test_measurement_after_discovery_routes_correctly(integration) -> None:
    """average_power after device_found routes data-update signal and feeds VHH."""
    d, send, entry, vhh = integration
    entry.data = {CFG_ROLES: {SENSOR_MAC: "house-net"}}

    await d.on_device_event(_sensor_found(SENSOR_MAC, role="house-net"))
    send.reset_mock()

    await d.on_device_event(_average_power(SENSOR_MAC, "house-net", 1200.0))

    signals = _signals_sent(send)
    data_signal = f"{DATA_UPDATE_SIGNAL_PREFIX}{SENSOR_MAC}_average_power"
    assert data_signal in signals
    vhh.process_average_power_event.assert_awaited_once()


async def test_summation_after_discovery_routes_correctly(integration) -> None:
    """summation_energy after device_found routes data-update signal and feeds VHH."""
    d, send, entry, vhh = integration
    entry.data = {CFG_ROLES: {SENSOR_MAC: "house-net"}}

    await d.on_device_event(_sensor_found(SENSOR_MAC, role="house-net"))
    send.reset_mock()

    await d.on_device_event(_summation(SENSOR_MAC, "house-net", 9_000_000))

    signals = _signals_sent(send)
    data_signal = f"{DATA_UPDATE_SIGNAL_PREFIX}{SENSOR_MAC}_summation_energy"
    assert data_signal in signals
    vhh.process_summation_event.assert_awaited_once()


async def test_role_update_signal_sent_when_measurement_reveals_new_role(
    integration,
) -> None:
    """A measurement from a known MAC whose role differs from entry.data fires ROLE_UPDATE_SIGNAL."""
    d, send, entry, _vhh = integration
    # Sensor known but with no persisted role.
    entry.data = {CFG_ROLES: {}}
    d.sensors[SENSOR_MAC] = None

    await d.on_device_event(_average_power(SENSOR_MAC, "solar", 2500.0))

    signals = _signals_sent(send)
    assert ROLE_UPDATE_SIGNAL in signals
    role_call = next(c for c in send.call_args_list if c.args[1] == ROLE_UPDATE_SIGNAL)
    assert role_call.args[2] == SENSOR_MAC
    assert role_call.args[3] == "solar"


async def test_no_role_update_signal_when_role_already_matches(integration) -> None:
    """No ROLE_UPDATE_SIGNAL when the measurement role matches the persisted role."""
    d, send, entry, _vhh = integration
    entry.data = {CFG_ROLES: {SENSOR_MAC: "house-net"}}
    d.sensors[SENSOR_MAC] = "house-net"

    await d.on_device_event(_average_power(SENSOR_MAC, "house-net", 800.0))

    assert ROLE_UPDATE_SIGNAL not in _signals_sent(send)


async def test_late_discovery_via_measurement(integration) -> None:
    """A measurement from a MAC never seen via device_found triggers CREATE_SENSOR_SIGNAL.

    This covers the path where sensor data arrives before device_found fires —
    common when a sensor relays through a plug that was already subscribed.
    """
    d, send, entry, _vhh = integration
    entry.data = {CFG_ROLES: {}}

    assert SENSOR_MAC not in d.sensors
    assert SENSOR_MAC not in d.plugs

    await d.on_device_event(_average_power(SENSOR_MAC, "water", 0.0))

    assert CREATE_SENSOR_SIGNAL in _signals_sent(send)
    assert SENSOR_MAC in d.sensors


# ---------------------------------------------------------------------------
# device_lost
# ---------------------------------------------------------------------------


async def test_device_lost_does_not_remove_mac_from_tracker(integration) -> None:
    """device_lost must not remove the MAC from plugs/sensors.

    The library handles reconnection; we must not send CREATE_*_SIGNAL again
    when the device reconnects, so the MAC must stay tracked.
    """
    d, send, _entry, _vhh = integration

    await d.on_device_event(_plug_found(PLUG_MAC))
    send.reset_mock()

    await d.on_device_event(_device_lost(PLUG_MAC))

    assert PLUG_MAC in d.plugs
    assert not _signals_sent(send)

    # When the plug reappears after being lost, no duplicate CREATE_PLUG_SIGNAL.
    await d.on_device_event(_plug_found(PLUG_MAC))
    assert CREATE_PLUG_SIGNAL not in _signals_sent(send)


# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------


async def test_disconnect_after_full_lifecycle(integration, mock_devices) -> None:
    """disconnect() unsubscribes every MAC discovered during a full session."""
    d, _send, _entry, _vhh = integration

    await d.on_device_event(_plug_found(PLUG_MAC))
    await d.on_device_event(_sensor_found(SENSOR_MAC, role="house-net"))
    await d.on_device_event(_sensor_found(SOLAR_MAC, role="solar"))

    await d.disconnect()

    unsubscribed = {c.args[0] for c in mock_devices.unsubscribe.call_args_list}
    assert PLUG_MAC in unsubscribed
    assert SENSOR_MAC in unsubscribed
    assert SOLAR_MAC in unsubscribed


async def test_disconnect_empty_is_safe(integration, mock_devices) -> None:
    """disconnect() on a dispatcher that never discovered any devices does not raise."""
    d, _send, _entry, _vhh = integration

    assert not d.plugs
    assert not d.sensors

    await d.disconnect()  # must not raise

    mock_devices.unsubscribe.assert_not_called()


# ---------------------------------------------------------------------------
# Multi-sensor role independence
# ---------------------------------------------------------------------------


async def test_role_changes_are_independent_per_mac(integration) -> None:
    """A role change on one sensor must not affect signals for another sensor's MAC."""
    d, send, entry, _vhh = integration
    entry.data = {CFG_ROLES: {SENSOR_MAC: "house-net", SOLAR_MAC: "solar"}}

    await d.on_device_event(_sensor_found(SENSOR_MAC, role="house-net"))
    await d.on_device_event(_sensor_found(SOLAR_MAC, role="solar"))
    send.reset_mock()

    # Measurement for SENSOR_MAC with unchanged role — no ROLE_UPDATE_SIGNAL.
    await d.on_device_event(_average_power(SENSOR_MAC, "house-net", 500.0))
    assert ROLE_UPDATE_SIGNAL not in _signals_sent(send)

    send.reset_mock()

    # Measurement for SOLAR_MAC with a role change — ROLE_UPDATE_SIGNAL only for SOLAR_MAC.
    await d.on_device_event(_average_power(SOLAR_MAC, "water", 0.0))
    role_calls = [c for c in send.call_args_list if c.args[1] == ROLE_UPDATE_SIGNAL]
    assert len(role_calls) == 1
    assert role_calls[0].args[2] == SOLAR_MAC
