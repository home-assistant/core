"""Tests for Powersensor's zeroconf discovery service."""

import asyncio
import importlib
from ipaddress import ip_address
from unittest.mock import Mock, call

import pytest
from zeroconf import BadTypeInNameException, ServiceInfo

from homeassistant.components.powersensor import PowersensorDiscoveryService
from homeassistant.components.powersensor.const import (
    ZEROCONF_ADD_PLUG_SIGNAL,
    ZEROCONF_REMOVE_PLUG_SIGNAL,
    ZEROCONF_UPDATE_PLUG_SIGNAL,
)
import homeassistant.components.powersensor.powersensor_discovery_service as mod
from homeassistant.components.powersensor.powersensor_discovery_service import (
    PowersensorServiceListener,
)
from homeassistant.core import HomeAssistant

MAC = "a4cf1218f158"


@pytest.fixture
def mock_service_info():
    """Minimal ServiceInfo representing a Powersensor gateway."""
    return ServiceInfo(
        addresses=[ip_address("192.168.0.33").packed],
        server=f"Powersensor-gateway-{MAC}-civet.local.",
        name=f"Powersensor-gateway-{MAC}-civet._powersensor._udp.local.",
        port=49476,
        type_="_powersensor._udp.local.",
        properties={
            "version": "1",
            "id": f"{MAC}",
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_dispatch(monkeypatch, service):
    """Patch PowersensorServiceListener.dispatch and return the mock."""
    mock_send = Mock()
    monkeypatch.setattr(service.__class__, "dispatch", lambda self, *a: mock_send(*a))
    return mock_send


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discovery_add(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_service_info
) -> None:
    """Test that add_service retrieves info and dispatches ZEROCONF_ADD_PLUG_SIGNAL."""
    service = PowersensorServiceListener(hass)
    mock_send = Mock()
    monkeypatch.setattr(
        PowersensorServiceListener, "dispatch", lambda self, *a: mock_send(*a)
    )

    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = zc_info

    service.add_service(mock_zc, zc_info.type, zc_info.name)
    mock_zc.get_service_info.assert_called_once_with(zc_info.type, zc_info.name)

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    mock_send.assert_called_once_with(
        ZEROCONF_ADD_PLUG_SIGNAL, service._plugs[zc_info.name]
    )


@pytest.mark.asyncio
async def test_discovery_add_and_remove(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_service_info
) -> None:
    """Test that remove_service dispatches ZEROCONF_REMOVE_PLUG_SIGNAL after debounce.

    dispatch() now calls dispatcher_send (the thread-safe sync API), so we patch
    that for add/update signals.  The removal timer fires _do_remove on the event
    loop, which still calls async_dispatcher_send directly, so we patch that too.
    Both patches append to the same calls list so the test can assert on ordering.
    """

    calls = []
    monkeypatch.setattr(mod, "dispatcher_send", lambda hass, *a: calls.append(a))
    monkeypatch.setattr(mod, "async_dispatcher_send", lambda hass, *a: calls.append(a))

    service = PowersensorServiceListener(hass, debounce_timeout=3)
    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = zc_info

    service.add_service(mock_zc, zc_info.type, zc_info.name)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0] == (ZEROCONF_ADD_PLUG_SIGNAL, service._plugs[zc_info.name])

    data = service._plugs[zc_info.name].copy()
    calls.clear()

    service.remove_service(mock_zc, zc_info.type, zc_info.name)
    assert len(calls) == 0

    await asyncio.sleep(service._debounce_seconds + 1)
    for _ in range(3):
        await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0] == (ZEROCONF_REMOVE_PLUG_SIGNAL, zc_info.name, data)


@pytest.mark.asyncio
async def test_discovery_remove_without_add(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_service_info
) -> None:
    """Test that remove_service for an unseen plug dispatches REMOVE signal with None data."""

    calls = []
    monkeypatch.setattr(mod, "dispatcher_send", lambda hass, *a: calls.append(a))
    monkeypatch.setattr(mod, "async_dispatcher_send", lambda hass, *a: calls.append(a))

    service = PowersensorServiceListener(hass, debounce_timeout=3)
    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = zc_info

    service.remove_service(mock_zc, zc_info.type, zc_info.name)
    mock_zc.get_service_info.assert_not_called()
    assert len(calls) == 0

    await asyncio.sleep(service._debounce_seconds + 1)
    for _ in range(3):
        await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0] == (ZEROCONF_REMOVE_PLUG_SIGNAL, zc_info.name, None)


@pytest.mark.asyncio
async def test_discovery_remove_cancel(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_service_info
) -> None:
    """Test that a re-add cancels a pending removal.

    Verifies that:
    - _pending_removals has one entry immediately after remove_service.
    - A subsequent add_service clears the pending removal.
    - The REMOVE signal is never sent.
    """
    service = PowersensorServiceListener(hass, debounce_timeout=3)
    mock_send = Mock()
    monkeypatch.setattr(
        PowersensorServiceListener, "dispatch", lambda self, *a: mock_send(*a)
    )

    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = zc_info

    service.add_service(mock_zc, zc_info.type, zc_info.name)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Reset mock to track only the remove/re-add phase.
    mock_send = Mock()
    monkeypatch.setattr(
        PowersensorServiceListener, "dispatch", lambda self, *a: mock_send(*a)
    )

    assert len(service._pending_removals) == 0
    service.remove_service(mock_zc, zc_info.type, zc_info.name)
    mock_send.assert_not_called()
    # call_soon_threadsafe schedules _schedule_removal_on_loop asynchronously;
    # drain the loop so the callback runs before we inspect _pending_removals.
    await hass.async_block_till_done()
    assert len(service._pending_removals) == 1

    await asyncio.sleep(0.5)

    # Re-adding should cancel the pending removal.
    service.add_service(mock_zc, zc_info.type, zc_info.name)
    assert mock_zc.get_service_info.call_count == 2
    mock_zc.get_service_info.assert_has_calls(
        [call(zc_info.type, zc_info.name), call(zc_info.type, zc_info.name)]
    )

    await asyncio.sleep(0.5)
    assert len(service._pending_removals) == 0


@pytest.mark.asyncio
async def test_discovery_add_and_two_remove_calls(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_service_info
) -> None:
    """Test that a second remove_service call during the debounce is a no-op.

    Verifies that the REMOVE signal fires exactly once even if remove_service is
    called twice before the debounce window expires.
    """

    calls = []
    monkeypatch.setattr(mod, "dispatcher_send", lambda hass, *a: calls.append(a))
    monkeypatch.setattr(mod, "async_dispatcher_send", lambda hass, *a: calls.append(a))

    service = PowersensorServiceListener(hass, debounce_timeout=2)
    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = zc_info

    service.add_service(mock_zc, zc_info.type, zc_info.name)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert len(calls) == 1

    data = service._plugs[zc_info.name].copy()
    calls.clear()

    service.remove_service(mock_zc, zc_info.type, zc_info.name)
    assert len(calls) == 0
    for _ in range(3):
        await hass.async_block_till_done()
    assert len(service._pending_removals) == 1

    await asyncio.sleep(service._debounce_seconds // 2 + 1)
    service.remove_service(mock_zc, zc_info.type, zc_info.name)
    await asyncio.sleep(service._debounce_seconds // 2 + 1)
    for _ in range(3):
        await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0] == (ZEROCONF_REMOVE_PLUG_SIGNAL, zc_info.name, data)


@pytest.mark.asyncio
async def test_discovery_update(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_service_info
) -> None:
    """Test that update_service dispatches ZEROCONF_UPDATE_PLUG_SIGNAL with new address."""
    service = PowersensorServiceListener(hass, debounce_timeout=2)
    mock_send = Mock()
    monkeypatch.setattr(
        PowersensorServiceListener, "dispatch", lambda self, *a: mock_send(*a)
    )

    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = zc_info

    service.add_service(mock_zc, zc_info.type, zc_info.name)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    mock_send = Mock()
    monkeypatch.setattr(
        PowersensorServiceListener, "dispatch", lambda self, *a: mock_send(*a)
    )

    updated_info = ServiceInfo(
        addresses=[ip_address("192.168.0.34").packed],
        server=f"Powersensor-gateway-{MAC}-civet.local.",
        name=f"Powersensor-gateway-{MAC}-civet._powersensor._udp.local.",
        port=49476,
        type_="_powersensor._udp.local.",
        properties={"version": "1", "id": f"{MAC}"},
    )
    mock_zc.get_service_info.return_value = updated_info
    service.update_service(mock_zc, updated_info.type, updated_info.name)

    for _ in range(3):
        await hass.async_block_till_done()

    mock_send.assert_called_once_with(
        ZEROCONF_UPDATE_PLUG_SIGNAL, service._plugs[zc_info.name]
    )
    assert service._plugs[zc_info.name]["addresses"] == ["192.168.0.34"]


@pytest.mark.asyncio
async def test_discovery_dispatcher(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that dispatch() calls dispatcher_send with the correct arguments.

    dispatch() uses dispatcher_send (the thread-safe sync API) rather than
    async_dispatcher_send, so we patch that symbol at the module level.
    dispatcher_send has the same signature as async_dispatcher_send:
    (hass, signal, *args).
    """
    mod = importlib.import_module(
        "homeassistant.components.powersensor.powersensor_discovery_service"
    )
    mock_send = Mock()
    monkeypatch.setattr(mod, "dispatcher_send", mock_send)
    service = mod.PowersensorServiceListener(hass, debounce_timeout=4)
    service.dispatch("mock_signal", 1, 2, 3, 4)
    mock_send.assert_called_once_with(hass, "mock_signal", 1, 2, 3, 4)


@pytest.mark.asyncio
async def test_discovery_service_early_exit(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that start() is a no-op when the service is already running."""
    service = PowersensorDiscoveryService(hass)
    service.running = True
    await service.start()

    # Nothing should have been initialised because we exited early.
    assert service.listener is None
    assert service.browser is None


@pytest.mark.asyncio
async def test_discovery_service_stop(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that stop() cancels the browser and clears state.

    The old implementation stored a _task that needed explicit cancellation.
    The refactored implementation has no such task; this test verifies that
    stop() still tidies up browser and running state correctly.
    """
    service = PowersensorDiscoveryService(hass)
    service.running = True

    mock_browser = Mock()
    mock_browser.cancel = Mock()
    service.browser = mock_browser

    await service.stop()

    mock_browser.cancel.assert_called_once()
    assert service.browser is None
    assert not service.running


@pytest.mark.asyncio
@pytest.mark.parametrize("exc", [BadTypeInNameException, OSError, NotImplementedError])
async def test_extract_plug_info_get_service_info_exception(
    hass: HomeAssistant, mock_service_info, exc
) -> None:
    """Test that exceptions from get_service_info are caught and return False.

    Lines 172-174 of powersensor_discovery_service.py: BadTypeInNameException,
    OSError, and NotImplementedError are all caught, logged, and cause
    _extract_plug_info to return False without populating _plugs.
    """
    service = PowersensorServiceListener(hass)
    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.side_effect = exc

    result = service._extract_plug_info(mock_zc, zc_info.type, zc_info.name)

    assert result is False
    assert zc_info.name not in service._plugs


@pytest.mark.asyncio
async def test_extract_plug_info_no_service_info_returns_false(
    hass: HomeAssistant, mock_service_info
) -> None:
    """Test that a None result from get_service_info returns False.

    Line 177-178 of powersensor_discovery_service.py: if get_service_info
    returns a falsy value, _extract_plug_info returns False without
    populating _plugs.
    """
    service = PowersensorServiceListener(hass)
    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = None

    result = service._extract_plug_info(mock_zc, zc_info.type, zc_info.name)

    assert result is False
    assert zc_info.name not in service._plugs


@pytest.mark.asyncio
async def test_second_remove_service_skipped_when_already_pending(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_service_info
) -> None:
    """Test that remove_service is a no-op if a removal is already pending.

    The _pending_removals check in remove_service only fires if
    _schedule_removal_on_loop has already run and populated _pending_removals.
    We must await hass.async_block_till_done() after the first remove_service
    to flush call_soon_threadsafe onto the loop before the second call.
    """
    service = PowersensorServiceListener(hass)
    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = zc_info

    service.add_service(mock_zc, zc_info.type, zc_info.name)

    threadsafe_calls = []
    original = hass.loop.call_soon_threadsafe

    def counting_threadsafe(fn, *args):
        threadsafe_calls.append((fn, *args))
        return original(fn, *args)

    monkeypatch.setattr(hass.loop, "call_soon_threadsafe", counting_threadsafe)

    # First removal — schedules _schedule_removal_on_loop via call_soon_threadsafe
    service.remove_service(mock_zc, zc_info.type, zc_info.name)
    assert len(threadsafe_calls) == 1

    # Flush the loop so _schedule_removal_on_loop runs and populates _pending_removals
    await hass.async_block_till_done()
    assert len(service._pending_removals) == 1

    # Second removal — _pending_removals is now populated so line 103 fires
    service.remove_service(mock_zc, zc_info.type, zc_info.name)
    assert len(threadsafe_calls) == 1  # no new call_soon_threadsafe


async def test_schedule_removal_on_loop_recheck_skips_duplicate(
    hass: HomeAssistant, mock_service_info
) -> None:
    """Test that _schedule_removal_on_loop is a no-op if already pending.

    If two call_soon_threadsafe calls are queued before the loop
    drains either of them, _schedule_removal_on_loop runs twice for the same
    name. The second run finds the name already in _pending_removals and returns
    immediately without scheduling a second debounce timer.
    """
    service = PowersensorServiceListener(hass)
    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = zc_info

    service.add_service(mock_zc, zc_info.type, zc_info.name)

    # Queue _schedule_removal_on_loop twice before the loop drains either —
    # simulating two rapid remove_service calls from the zeroconf thread.
    hass.loop.call_soon_threadsafe(service._schedule_removal_on_loop, zc_info.name)
    hass.loop.call_soon_threadsafe(service._schedule_removal_on_loop, zc_info.name)

    # Now drain — both run, but the second hits line 128 and returns immediately.
    await hass.async_block_till_done()

    # Only one debounce timer should have been scheduled.
    assert len(service._pending_removals) == 1
