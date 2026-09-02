"""Tests for the Easywave coordinator."""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from easywave_home_control.codec import (
    ButtonFunction,
    ButtonPushEvent,
    ButtonReleaseEvent,
)
from easywave_home_control.codec.events import EasywaveButton
import pytest

from homeassistant.components.easywave.const import (
    DEVICE_SCAN_INTERVAL,
    DOMAIN,
    EVENT_EASYWAVE,
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_BATTERY_NORMAL,
    EVENT_TYPE_BUTTON_PRESS,
    EVENT_TYPE_BUTTON_RELEASE,
    EVENT_TYPE_GATEWAY_CONNECTED,
    EVENT_TYPE_GATEWAY_DISCONNECTED,
)
from homeassistant.components.easywave.coordinator import EasywaveCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import (
    MOCK_GATEWAY_TITLE,
    MOCK_TRANSMITTER_DEVICE_ID,
    MOCK_TRANSMITTER_SERIAL,
    _entry_with_subentries,
    _transmitter_device_record,
    mock_easywave_transceiver,
)

from tests.common import MockConfigEntry, async_capture_events


@pytest.fixture
def mock_transceiver() -> MagicMock:
    """Return a mock RX11Transceiver at the hardware boundary."""
    return mock_easywave_transceiver()


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_GATEWAY_TITLE,
        data={"device_path": "/dev/ttyACM0"},
    )


@pytest.fixture
def coordinator(
    hass: HomeAssistant,
    mock_transceiver: MagicMock,
    mock_entry: MockConfigEntry,
) -> EasywaveCoordinator:
    """Return an EasywaveCoordinator instance."""
    mock_entry.add_to_hass(hass)
    mock_entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    return EasywaveCoordinator(hass, mock_transceiver, mock_entry)


def test_coordinator_init(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
    mock_entry: MockConfigEntry,
) -> None:
    """Test coordinator initialisation."""
    assert coordinator.transceiver is mock_transceiver
    assert coordinator.config_entry is mock_entry
    assert coordinator.name == DOMAIN
    assert coordinator.update_interval == DEVICE_SCAN_INTERVAL
    assert coordinator.is_offline is False


def test_coordinator_init_offline(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
) -> None:
    """Test coordinator initialises as offline when transceiver not connected."""
    mock_entry.add_to_hass(hass)
    transceiver = MagicMock()
    transceiver.is_connected = False
    coord = EasywaveCoordinator(hass, transceiver, mock_entry)
    assert coord.is_offline is True


async def test_first_refresh_registers_gateway_versions(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Successful first refresh connects and registers gateway versions."""
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.is_offline is False
    mock_transceiver.connect.assert_awaited_once()
    mock_transceiver.set_disconnect_callback.assert_called_once()
    mock_transceiver.set_connected_callback.assert_called_once()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, coordinator.config_entry.entry_id),
        coordinator.config_entry.entry_id,
    )
    assert device is not None
    assert device.hw_version == "1.0"
    assert device.sw_version == "2.0"


async def test_first_refresh_raises_not_ready_when_connect_fails(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """First refresh raises ConfigEntryNotReady when the transceiver cannot connect."""
    mock_transceiver.connect = AsyncMock(return_value=False)
    mock_transceiver.reconnect = AsyncMock(return_value=False)

    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()

    assert coordinator.last_update_success is False
    mock_transceiver.set_disconnect_callback.assert_not_called()


async def test_first_refresh_raises_update_failed_on_connect_error(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """First refresh raises ConfigEntryNotReady when connect raises."""
    mock_transceiver.connect = AsyncMock(side_effect=OSError("port error"))

    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_transceiver_disconnect_marks_coordinator_offline(
    hass: HomeAssistant,
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Transceiver disconnect callback marks the coordinator offline."""
    await coordinator.async_config_entry_first_refresh()
    coordinator.is_offline = False
    disconnect_callback = mock_transceiver.set_disconnect_callback.call_args[0][0]

    with patch.object(hass.loop, "call_soon_threadsafe") as mock_schedule:
        disconnect_callback()
        await hass.async_block_till_done()

    mock_schedule.assert_not_called()
    assert coordinator.is_offline is True
    assert coordinator.data == {
        "is_connected": False,
        "device_path": None,
    }


async def test_transceiver_disconnect_is_noop_when_already_offline(
    hass: HomeAssistant,
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Repeated disconnect callbacks do not change an offline coordinator."""
    await coordinator.async_config_entry_first_refresh()
    disconnect_callback = mock_transceiver.set_disconnect_callback.call_args[0][0]
    coordinator.is_offline = True

    disconnect_callback()
    await hass.async_block_till_done()

    assert coordinator.is_offline is True


async def test_refresh_returns_connected_data_when_online(
    coordinator: EasywaveCoordinator,
) -> None:
    """Periodic refresh returns connected data when online."""
    await coordinator.async_config_entry_first_refresh()

    await coordinator.async_refresh()

    assert coordinator.data == {
        "is_connected": True,
        "device_path": "/dev/ttyACM0",
    }


async def test_refresh_reconnects_and_updates_gateway_versions(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Periodic refresh reconnects from offline and updates gateway versions."""
    device_registry.async_get_or_create(
        config_entry_id=coordinator.config_entry.entry_id,
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name="RX11 USB Transceiver",
    )

    async def receive_side_effect(timeout: float = 30.0) -> None:
        raise asyncio.CancelledError

    mock_transceiver.receive_telegram = AsyncMock(side_effect=receive_side_effect)
    await coordinator.async_config_entry_first_refresh()
    coordinator.register_transmitter_entities([MagicMock()])
    await coordinator.hass.async_block_till_done(wait_background_tasks=True)
    coordinator.is_offline = True
    mock_transceiver.reconnect = AsyncMock(return_value=True)
    mock_transceiver.is_connected = True
    mock_transceiver.device_path = "/dev/ttyACM0"
    mock_transceiver.hw_version = "RX11 v1.0"
    mock_transceiver.fw_version = "FW 2.3.4"

    await coordinator.async_refresh()

    mock_transceiver.reconnect.assert_awaited_once()
    assert coordinator.is_offline is False
    assert coordinator.data == {
        "is_connected": True,
        "device_path": "/dev/ttyACM0",
    }

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, coordinator.config_entry.entry_id),
        coordinator.config_entry.entry_id,
    )
    assert device is not None
    assert device.hw_version == "RX11 v1.0"
    assert device.sw_version == "FW 2.3.4"


async def test_refresh_stays_offline_when_reconnect_fails(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Periodic refresh stays offline when reconnect fails."""
    await coordinator.async_config_entry_first_refresh()
    coordinator.is_offline = True
    mock_transceiver.reconnect = AsyncMock(return_value=False)

    await coordinator.async_refresh()

    mock_transceiver.reconnect.assert_awaited_once()
    assert coordinator.is_offline is True
    assert coordinator.data == {"is_connected": False, "device_path": None}


async def test_refresh_skips_reconnect_while_learning(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Periodic refresh does not reconnect during a device learning session."""
    await coordinator.async_config_entry_first_refresh()
    coordinator.is_offline = True
    assert await coordinator.begin_learning() is True

    await coordinator.async_refresh()

    mock_transceiver.reconnect.assert_not_called()
    assert coordinator.is_offline is True
    coordinator.end_learning()


async def test_connected_callback_restores_online_state(
    hass: HomeAssistant,
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Transceiver connect callbacks restore the coordinator online state."""
    device_registry.async_get_or_create(
        config_entry_id=coordinator.config_entry.entry_id,
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name="RX11 USB Transceiver",
    )
    await coordinator.async_config_entry_first_refresh()
    coordinator.is_offline = True
    mock_transceiver.is_connected = True
    mock_transceiver.device_path = "/dev/ttyACM0"
    mock_transceiver.hw_version = "RX11 v1.0"
    mock_transceiver.fw_version = "FW 2.3.4"
    connected_callback = mock_transceiver.set_connected_callback.call_args[0][0]

    connected_callback()
    await hass.async_block_till_done()

    assert coordinator.is_offline is False
    assert coordinator.data == {
        "is_connected": True,
        "device_path": "/dev/ttyACM0",
    }
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, coordinator.config_entry.entry_id),
        coordinator.config_entry.entry_id,
    )
    assert device is not None
    assert device.hw_version == "RX11 v1.0"
    assert device.sw_version == "FW 2.3.4"


async def test_refresh_detects_lost_connection(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Periodic refresh detects connection loss during polling."""
    await coordinator.async_config_entry_first_refresh()
    mock_transceiver.is_connected = False

    await coordinator.async_refresh()

    assert coordinator.is_offline is True
    assert coordinator.data == {"is_connected": False, "device_path": None}


async def test_refresh_reraises_update_failed(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """UpdateFailed from reconnect is recorded during refresh."""
    await coordinator.async_config_entry_first_refresh()
    coordinator.is_offline = True
    mock_transceiver.reconnect = AsyncMock(side_effect=UpdateFailed("fail"))

    await coordinator.async_refresh()

    assert coordinator.is_offline is True
    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_refresh_wraps_reconnect_os_error_in_update_failed(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """OS errors during reconnect are wrapped in UpdateFailed."""
    await coordinator.async_config_entry_first_refresh()
    coordinator.is_offline = True
    mock_transceiver.reconnect = AsyncMock(side_effect=OSError("boom"))

    await coordinator.async_refresh()

    assert coordinator.is_offline is True
    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert str(coordinator.last_exception) == "Update failed: boom"


async def test_refresh_wraps_os_error_in_update_failed(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """OS errors while reading connection state are wrapped in UpdateFailed."""
    await coordinator.async_config_entry_first_refresh()
    type(mock_transceiver).is_connected = PropertyMock(side_effect=OSError("boom"))

    await coordinator.async_refresh()

    assert coordinator.is_offline is True
    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert str(coordinator.last_exception) == "Update failed: boom"


async def test_telegram_listener_restarts_after_suspend_resume(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Suspending and resuming the listener restarts telegram polling."""

    async def receive_side_effect(timeout: float = 30.0) -> None:
        raise asyncio.CancelledError

    mock_transceiver.receive_telegram = AsyncMock(side_effect=receive_side_effect)

    await coordinator.async_config_entry_first_refresh()
    entity = MagicMock()
    try:
        coordinator.register_sensor_entities([entity])
        await coordinator.hass.async_block_till_done(wait_background_tasks=True)

        await coordinator.suspend_telegram_listener()
        mock_transceiver.receive_telegram.reset_mock()
        coordinator.resume_telegram_listener()
        await coordinator.hass.async_block_till_done(wait_background_tasks=True)

        mock_transceiver.receive_telegram.assert_called()
    finally:
        await coordinator.suspend_telegram_listener()
        await coordinator.async_shutdown()


async def test_transceiver_connected_updates_gateway_device(
    hass: HomeAssistant,
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Transceiver connect callback refreshes gateway device metadata."""
    device_registry.async_get_or_create(
        config_entry_id=coordinator.config_entry.entry_id,
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name="RX11 USB Transceiver",
    )
    await coordinator.async_config_entry_first_refresh()
    mock_transceiver.hw_version = "RX11 v2.0"
    connected_callback = mock_transceiver.set_connected_callback.call_args[0][0]

    connected_callback()
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, coordinator.config_entry.entry_id),
        coordinator.config_entry.entry_id,
    )
    assert device is not None
    assert device.hw_version == "RX11 v2.0"


async def test_async_shutdown(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test clean shutdown disposes transceiver."""
    await coordinator.async_shutdown()

    mock_transceiver.dispose.assert_awaited_once()


async def test_async_shutdown_error(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test shutdown handles errors gracefully."""
    mock_transceiver.dispose = AsyncMock(side_effect=OSError("port busy"))

    await coordinator.async_shutdown()

    mock_transceiver.dispose.assert_awaited_once()


async def test_ensure_telegram_listener_noops_when_offline(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Listener startup is skipped while the coordinator is offline."""
    await coordinator.async_config_entry_first_refresh()
    coordinator.is_offline = True

    coordinator.ensure_telegram_listener()

    assert coordinator._listener_task is None


async def test_fire_device_event_ignores_missing_device_registry_entry(
    hass: HomeAssistant,
    coordinator: EasywaveCoordinator,
) -> None:
    """Device events are not fired when the target device is not registered."""
    await coordinator.async_config_entry_first_refresh()
    events = []

    def capture_event(event: object) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_EASYWAVE, capture_event)
    coordinator.fire_device_event("missing_device_id", "button_press", subtype="a")
    await hass.async_block_till_done()

    assert events == []


async def test_async_shutdown_awaits_cancelled_listener(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Shutdown waits for a cancelled telegram listener task."""
    started = asyncio.Event()
    proceed = asyncio.Event()

    async def receive_side_effect(timeout: float = 30.0) -> None:
        started.set()
        await proceed.wait()

    mock_transceiver.receive_telegram = AsyncMock(side_effect=receive_side_effect)
    await coordinator.async_config_entry_first_refresh()
    coordinator.register_sensor_entities([MagicMock()])
    await asyncio.wait_for(started.wait(), timeout=1)

    await coordinator.async_shutdown()

    mock_transceiver.dispose.assert_awaited_once()


async def test_ensure_telegram_listener_skips_running_task(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Listener startup is skipped when a listener task is already running."""
    started = asyncio.Event()
    proceed = asyncio.Event()

    async def receive_side_effect(timeout: float = 30.0) -> None:
        started.set()
        await proceed.wait()

    mock_transceiver.receive_telegram = AsyncMock(side_effect=receive_side_effect)
    await coordinator.async_config_entry_first_refresh()
    coordinator.register_sensor_entities([MagicMock()])
    await asyncio.wait_for(started.wait(), timeout=1)

    first_task = coordinator._listener_task
    coordinator.ensure_telegram_listener()

    assert coordinator._listener_task is first_task
    proceed.set()
    await coordinator.async_shutdown()


async def test_ensure_telegram_listener_noops_without_entities(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Listener startup is skipped when no entities are registered."""
    await coordinator.async_config_entry_first_refresh()

    coordinator.ensure_telegram_listener()

    assert coordinator._listener_task is None


async def test_start_telegram_listener_noops_without_entities(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Direct listener startup is skipped when no entities are registered."""
    await coordinator.async_config_entry_first_refresh()

    coordinator._start_telegram_listener()

    assert coordinator._listener_task is None


async def test_clear_listener_task_skips_foreign_running_task(
    hass: HomeAssistant,
    coordinator: EasywaveCoordinator,
) -> None:
    """Listener cleanup does not drop a newer replacement task."""

    async def _replacement_listener() -> None:
        await asyncio.Event().wait()

    replacement = hass.async_create_task(
        _replacement_listener(), "replacement_listener"
    )
    coordinator._listener_task = replacement

    async def old_finally() -> None:
        await coordinator._clear_listener_task()

    await hass.async_create_task(old_finally(), "old_finally")

    assert coordinator._listener_task is replacement
    replacement.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await replacement


async def test_clear_listener_task_clears_own_task(
    coordinator: EasywaveCoordinator,
) -> None:
    """Listener cleanup clears the task reference for the exiting loop."""

    async def own_loop() -> None:
        coordinator._listener_task = asyncio.current_task()
        await coordinator._clear_listener_task()

    await own_loop()

    assert coordinator._listener_task is None


async def test_begin_learning_rejects_second_session(
    coordinator: EasywaveCoordinator,
) -> None:
    """Only one device learning session can hold the hardware lock."""
    assert await coordinator.begin_learning() is True
    assert coordinator.is_learning_busy() is True
    assert await coordinator.begin_learning() is False
    coordinator.end_learning()
    assert coordinator.is_learning_busy() is False


async def test_listener_starts_for_configured_transmitter_without_entities(
    hass: HomeAssistant,
    mock_transceiver: MagicMock,
) -> None:
    """Listener starts when transmitters are configured but entities are disabled."""
    entry = _entry_with_subentries(_transmitter_device_record())
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    coordinator = EasywaveCoordinator(hass, mock_transceiver, entry)

    async def receive_side_effect(timeout: float = 30.0) -> None:
        raise asyncio.CancelledError

    mock_transceiver.receive_telegram = AsyncMock(side_effect=receive_side_effect)
    await coordinator.async_config_entry_first_refresh()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator._listener_task is not None
    await coordinator.async_shutdown()


async def test_dispatch_button_press_fires_event_without_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Button press device events fire for configured transmitters without entities."""
    entry = _entry_with_subentries(_transmitter_device_record())
    entry.add_to_hass(hass)
    transceiver = mock_easywave_transceiver()
    coordinator = EasywaveCoordinator(hass, transceiver, entry)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)},
        name="Test Transmitter",
    )
    events = []

    def capture_event(event: object) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_EASYWAVE, capture_event)

    coordinator._dispatch_button_push(
        ButtonPushEvent(
            transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
            button=EasywaveButton.A,
            function=ButtonFunction.DEFAULT,
            should_ignore=False,
        )
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["type"] == EVENT_TYPE_BUTTON_PRESS
    assert events[0].data["subtype"] == "a"


async def test_dispatch_button_release_fires_event_without_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Button release device events fire for configured transmitters without entities."""
    entry = _entry_with_subentries(_transmitter_device_record())
    entry.add_to_hass(hass)
    transceiver = mock_easywave_transceiver()
    coordinator = EasywaveCoordinator(hass, transceiver, entry)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)},
        name="Test Transmitter",
    )
    events = []

    def capture_event(event: object) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_EASYWAVE, capture_event)

    coordinator._dispatch_button_release(
        ButtonReleaseEvent(
            transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
        )
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["type"] == EVENT_TYPE_BUTTON_RELEASE
    assert events[0].data["subtype"] == "released"


async def test_dispatch_low_battery_fires_event_without_battery_entity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Battery-low device events fire without a battery sensor entity."""
    entry = _entry_with_subentries(_transmitter_device_record())
    entry.add_to_hass(hass)
    transceiver = mock_easywave_transceiver()
    coordinator = EasywaveCoordinator(hass, transceiver, entry)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)},
        name="Test Transmitter",
    )
    events = []

    def capture_event(event: object) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_EASYWAVE, capture_event)

    coordinator._dispatch_button_push(
        ButtonPushEvent(
            transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
            button=EasywaveButton.A,
            function=ButtonFunction.LOW_BATTERY,
            should_ignore=False,
        )
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["type"] == EVENT_TYPE_BATTERY_LOW
    assert events[0].data["subtype"] == "low"


async def test_unregister_transmitter_entity_keeps_listener_for_configured_device(
    hass: HomeAssistant,
    mock_transceiver: MagicMock,
) -> None:
    """Unregistering the last entity does not stop reception for configured transmitters."""
    entry = _entry_with_subentries(_transmitter_device_record())
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    coordinator = EasywaveCoordinator(hass, mock_transceiver, entry)

    async def receive_side_effect(timeout: float = 30.0) -> None:
        raise asyncio.CancelledError

    mock_transceiver.receive_telegram = AsyncMock(side_effect=receive_side_effect)
    await coordinator.async_config_entry_first_refresh()
    entity = MagicMock()
    coordinator.register_transmitter_entities([entity])
    await hass.async_block_till_done(wait_background_tasks=True)
    assert coordinator._listener_task is not None

    coordinator.unregister_transmitter_entity(entity)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator._listener_task is not None
    await coordinator.async_shutdown()


async def test_dispatch_battery_normal_fires_event_without_battery_entity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Battery-normal device events fire without a battery sensor entity."""
    entry = _entry_with_subentries(_transmitter_device_record())
    entry.add_to_hass(hass)
    transceiver = mock_easywave_transceiver()
    coordinator = EasywaveCoordinator(hass, transceiver, entry)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)},
        name="Test Transmitter",
    )
    events = []

    def capture_event(event: object) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_EASYWAVE, capture_event)

    coordinator._dispatch_button_push(
        ButtonPushEvent(
            transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
            button=EasywaveButton.A,
            function=ButtonFunction.LOW_BATTERY,
            should_ignore=False,
        )
    )
    coordinator._dispatch_button_push(
        ButtonPushEvent(
            transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
            button=EasywaveButton.A,
            function=ButtonFunction.DEFAULT,
            should_ignore=False,
        )
    )
    coordinator._dispatch_button_push(
        ButtonPushEvent(
            transmitter_serial=bytes.fromhex(MOCK_TRANSMITTER_SERIAL),
            button=EasywaveButton.A,
            function=ButtonFunction.DEFAULT,
            should_ignore=False,
        )
    )
    await hass.async_block_till_done()

    assert any(event.data["type"] == EVENT_TYPE_BATTERY_NORMAL for event in events)


async def test_gateway_connected_event_fires_from_coordinator_callback(
    hass: HomeAssistant,
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Gateway connected device events fire from coordinator callbacks."""
    device_registry.async_get_or_create(
        config_entry_id=coordinator.config_entry.entry_id,
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name="RX11 USB Transceiver",
    )
    await coordinator.async_config_entry_first_refresh()
    events = async_capture_events(hass, EVENT_EASYWAVE)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    coordinator._gateway_last_status = "disconnected"
    coordinator.is_offline = True
    mock_transceiver.is_connected = True
    connected_callback = mock_transceiver.set_connected_callback.call_args[0][0]

    connected_callback()
    await hass.async_block_till_done()

    assert any(event.data["type"] == EVENT_TYPE_GATEWAY_CONNECTED for event in events)


async def test_gateway_disconnected_event_fires_from_coordinator_callback(
    hass: HomeAssistant,
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Gateway disconnected device events fire from coordinator callbacks."""
    device_registry.async_get_or_create(
        config_entry_id=coordinator.config_entry.entry_id,
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name="RX11 USB Transceiver",
    )
    await coordinator.async_config_entry_first_refresh()
    events = async_capture_events(hass, EVENT_EASYWAVE)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    coordinator._gateway_last_status = "connected"
    disconnect_callback = mock_transceiver.set_disconnect_callback.call_args[0][0]

    disconnect_callback()
    await hass.async_block_till_done()

    assert any(
        event.data["type"] == EVENT_TYPE_GATEWAY_DISCONNECTED for event in events
    )


async def test_first_disconnect_after_setup_fires_gateway_event(
    hass: HomeAssistant,
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Successful setup baselines connected so the first disconnect can fire."""
    device_registry.async_get_or_create(
        config_entry_id=coordinator.config_entry.entry_id,
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name="RX11 USB Transceiver",
    )
    await coordinator.async_config_entry_first_refresh()

    assert coordinator._gateway_last_status == "connected"

    events = async_capture_events(hass, EVENT_EASYWAVE)
    disconnect_callback = mock_transceiver.set_disconnect_callback.call_args[0][0]
    disconnect_callback()
    await hass.async_block_till_done()

    assert any(
        event.data["type"] == EVENT_TYPE_GATEWAY_DISCONNECTED for event in events
    )
    assert coordinator._gateway_last_status == "disconnected"
