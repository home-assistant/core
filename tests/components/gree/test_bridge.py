"""Tests for Gree device binding, polling, and lifetime."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
from greeclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError
from greeclimate.network import Response
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN, HVACMode
from homeassistant.components.gree.const import UPDATE_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .common import async_setup_gree, build_device_mock

ENTITY_ID_1 = f"{CLIMATE_DOMAIN}.fake_device_1"
ENTITY_ID_2 = f"{CLIMATE_DOMAIN}.fake_device_2"


async def test_saved_endpoint_scans_before_binding(
    hass: HomeAssistant, device: Mock
) -> None:
    """A saved device binds once after opening the firmware discovery window."""
    calls = Mock()
    calls.attach_mock(device().bind, "bind")
    scanner = Mock(async_scan=AsyncMock(return_value={}))
    calls.attach_mock(scanner.async_scan, "scan")
    with patch(
        "homeassistant.components.gree.coordinator.async_get_discovery",
        return_value=scanner,
    ):
        entry = await async_setup_gree(hass)

    assert entry.state is ConfigEntryState.LOADED
    scanner.async_scan.assert_awaited_once_with(wait_for=0)
    device().bind.assert_awaited_once_with()
    assert [call[0] for call in calls.mock_calls] == ["scan", "bind"]
    assert entry.runtime_data.device is device()
    assert hass.states.get(ENTITY_ID_1).state == HVACMode.OFF


@pytest.mark.parametrize(
    "error", [DeviceNotBoundError, DeviceTimeoutError, OSError, TimeoutError]
)
async def test_bind_failure_does_not_publish_entities(
    hass: HomeAssistant, device: Mock, error: type[Exception]
) -> None:
    """A bind failure stays retryable and retires the failed device."""
    device().bind.side_effect = error
    scanner = Mock(async_scan=AsyncMock(return_value={}))
    with patch(
        "homeassistant.components.gree.coordinator.async_get_discovery",
        return_value=scanner,
    ):
        entry = await async_setup_gree(hass)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.async_all(CLIMATE_DOMAIN) == []
    device().bind.assert_awaited_once_with()
    scanner.async_scan.assert_awaited_once_with(wait_for=0)
    device().update_state.assert_not_awaited()
    device().close.assert_called_once_with()


async def test_initial_state_timeout_does_not_create_entities(
    hass: HomeAssistant, device: Mock
) -> None:
    """A first timeout without a valid state keeps the entry retryable."""
    device().has_valid_state = False
    device().raw_properties = {}
    device().update_state.side_effect = DeviceTimeoutError

    entry = await async_setup_gree(hass)
    device().bind.assert_awaited_once_with()
    device().update_state.assert_awaited_once_with()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.async_all(CLIMATE_DOMAIN) == []
    assert hass.states.async_all(SWITCH_DOMAIN) == []


async def test_initial_state_timeout_after_bind_response_is_allowed(
    hass: HomeAssistant, device: Mock
) -> None:
    """A valid response during binding allows a transient first timeout."""
    device().has_valid_state = False
    device().raw_properties = {}
    device().update_state.side_effect = DeviceTimeoutError

    async def bind_with_valid_state() -> None:
        device().has_valid_state = True
        device().emit_response(Response.RESULT)

    device().bind.side_effect = bind_with_valid_state

    entry = await async_setup_gree(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID_1).state == HVACMode.OFF
    device().update_state.assert_awaited_once_with()


async def test_coordinator_updates(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, device: Mock
) -> None:
    """Polling updates the entity from the device's public properties."""
    await async_setup_gree(hass)
    device().power = True

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID_1).state == HVACMode.AUTO


async def test_unload_one_device_leaves_other_connected(
    hass: HomeAssistant, device: Mock
) -> None:
    """Entries own independent coordinators and control paths."""
    first_device = device()
    first_entry = await async_setup_gree(hass)
    second_device = build_device_mock(
        name="fake-device-2", ipAddress="2.2.2.2", identifier="bbccdd223344"
    )
    device.return_value = second_device
    second_entry = await async_setup_gree(hass, second_device)

    assert first_entry.runtime_data is not second_entry.runtime_data
    assert await hass.config_entries.async_unload(first_entry.entry_id)
    first_device.close.assert_called_once_with()
    second_device.close.assert_not_called()
    assert second_entry.state is ConfigEntryState.LOADED
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {"entity_id": ENTITY_ID_2, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    second_device.push_state_update.assert_awaited_once_with()


async def test_shutdown_ignores_late_callbacks(
    hass: HomeAssistant, device: Mock
) -> None:
    """Repeated shutdown closes once and late callbacks cannot change state."""
    entry = await async_setup_gree(hass)
    coordinator = entry.runtime_data
    before = coordinator.data
    assert await hass.config_entries.async_unload(entry.entry_id)
    unloaded_state = hass.states.get(ENTITY_ID_1)
    assert unloaded_state is not None
    assert unloaded_state.state == STATE_UNAVAILABLE
    assert unloaded_state.attributes["restored"] is True
    await coordinator.async_shutdown()
    device().emit_response(Response.RESULT)
    await hass.async_block_till_done()

    assert coordinator.data is before
    device().close.assert_called_once_with()
    device().bind.assert_awaited_once_with()
    assert device().closed
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.data[CLIMATE_DOMAIN].get_entity(ENTITY_ID_1) is None
    assert hass.states.get(ENTITY_ID_1) is unloaded_state


async def test_shutdown_cancels_status_send(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device: Mock,
) -> None:
    """Unload cancels an in-flight status send."""
    entry = await async_setup_gree(hass)
    started = asyncio.Event()
    refresh: asyncio.Task[None] | None = None

    async def update_state() -> None:
        nonlocal refresh
        refresh = asyncio.current_task()
        started.set()
        await asyncio.Event().wait()

    device().update_state.side_effect = update_state
    freezer.tick(timedelta(seconds=UPDATE_INTERVAL + 1))
    async_fire_time_changed(hass)
    await started.wait()
    assert refresh is not None
    assert not refresh.done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    with pytest.raises(asyncio.CancelledError):
        await refresh

    unloaded_state = hass.states.get(ENTITY_ID_1)
    assert unloaded_state is not None
    assert unloaded_state.state == STATE_UNAVAILABLE
    assert unloaded_state.attributes["restored"] is True
    device().emit_response(Response.RESULT)
    await hass.async_block_till_done()

    device().close.assert_called_once_with()
    device().bind.assert_awaited_once_with()
    assert device().closed
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.data[CLIMATE_DOMAIN].get_entity(ENTITY_ID_1) is None
    assert hass.states.get(ENTITY_ID_1) is unloaded_state


async def test_shutdown_during_bind_does_not_retry(
    hass: HomeAssistant, device: Mock
) -> None:
    """Stopping during binding cancels setup without another bind."""
    started = asyncio.Event()

    async def bind() -> None:
        started.set()
        await asyncio.Event().wait()

    device().bind.side_effect = bind
    scanner = Mock(async_scan=AsyncMock(return_value={}))
    with patch(
        "homeassistant.components.gree.coordinator.async_get_discovery",
        return_value=scanner,
    ):
        setup = asyncio.create_task(async_setup_gree(hass))
        await started.wait()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        with pytest.raises(asyncio.CancelledError):
            await setup

    device().close.assert_called_once_with()
    device().bind.assert_awaited_once_with()
    scanner.async_scan.assert_awaited_once_with(wait_for=0)
    assert hass.states.async_all(CLIMATE_DOMAIN) == []


async def test_shutdown_rejects_late_bind_completion(
    hass: HomeAssistant, device: Mock
) -> None:
    """A bind suppressing cancellation cannot publish entities after shutdown."""
    started = asyncio.Event()

    async def bind() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            return

    device().bind.side_effect = bind
    setup = asyncio.create_task(async_setup_gree(hass))
    await started.wait()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    with pytest.raises(asyncio.CancelledError):
        await setup

    device().close.assert_called_once_with()
    device().bind.assert_awaited_once_with()
    device().update_state.assert_not_awaited()
    assert device().closed
    assert hass.states.async_all(CLIMATE_DOMAIN) == []


async def test_homeassistant_stop_closes_device(
    hass: HomeAssistant, device: Mock
) -> None:
    """HA stop retires a loaded device even before entry unload."""
    entry = await async_setup_gree(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    await entry.runtime_data.async_shutdown()

    device().close.assert_called_once_with()
    device().bind.assert_awaited_once_with()


async def test_shutdown_during_scan_does_not_bind(
    hass: HomeAssistant, device: Mock
) -> None:
    """Stop cancels the initial scan before binding can reopen the device."""
    started = asyncio.Event()

    async def scan(*, wait_for: int) -> dict:
        started.set()
        await asyncio.Event().wait()
        return {}

    scanner = Mock(async_scan=AsyncMock(side_effect=scan))
    with patch(
        "homeassistant.components.gree.coordinator.async_get_discovery",
        return_value=scanner,
    ):
        setup = asyncio.create_task(async_setup_gree(hass))
        await started.wait()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        with pytest.raises(asyncio.CancelledError):
            await setup

    device().close.assert_called_once_with()
    device().bind.assert_not_awaited()
    scanner.async_scan.assert_awaited_once_with(wait_for=0)
    assert hass.states.async_all(CLIMATE_DOMAIN) == []
