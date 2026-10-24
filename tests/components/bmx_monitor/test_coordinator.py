"""Test timer reads through the real Bluetooth coordinator and debouncer."""

from datetime import timedelta
import logging
from time import monotonic
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from sensor_state_data import SensorUpdate

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bmx_monitor import coordinator as coordinator_module
from homeassistant.components.bmx_monitor.const import (
    CONF_RATE_LIMIT,
    CONF_RATE_LIMIT_MODE,
    DOMAIN,
)
from homeassistant.components.bmx_monitor.coordinator import BMxBluetoothCoordinator
from homeassistant.components.bmx_monitor.device_data import BMxBluetoothDeviceData
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("mock_bluetooth")
ADDRESS = "AA:BB:CC:DD:EE:FF"


def make_coordinator(hass: HomeAssistant) -> BMxBluetoothCoordinator:
    """Create a real coordinator with only device I/O mocked."""
    return BMxBluetoothCoordinator(
        hass,
        logging.getLogger(__name__),
        address=ADDRESS,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=MagicMock(),
        needs_poll_method=MagicMock(return_value=True),
        poll_method=AsyncMock(return_value=SensorUpdate({}, {}, {}, {})),
        connectable=False,
    )


@pytest.mark.parametrize(
    ("state", "present", "info_available", "age", "needed", "expected"),
    [
        (CoreState.running, True, True, None, True, True),
        (CoreState.running, True, True, 59, True, False),
        (CoreState.running, True, True, 60, True, True),
        (CoreState.running, True, True, 120, False, False),
        (CoreState.starting, True, True, 120, True, False),
        (CoreState.running, False, True, 120, True, False),
        (CoreState.running, True, False, 120, True, False),
    ],
)
async def test_timer_poll_gates(
    hass: HomeAssistant,
    state: CoreState,
    present: bool,
    info_available: bool,
    age: int | None,
    needed: bool,
    expected: bool,
) -> None:
    """Gate timer reads on device presence, elapsed time and the poll schedule."""
    assert await async_setup_component(hass, "bluetooth", {})
    coordinator = make_coordinator(hass)
    coordinator._last_poll = 100 if age is not None else None
    coordinator._needs_poll_method.return_value = needed
    info = MagicMock(time=100)
    with (
        patch.object(hass, "state", state),
        patch.object(coordinator_module, "async_address_present", return_value=present),
        patch.object(
            coordinator_module,
            "async_last_service_info",
            return_value=info if info_available else None,
        ),
        patch.object(
            coordinator_module, "monotonic_time_coarse", return_value=100 + (age or 0)
        ),
        patch.object(coordinator._debounced_poll, "async_schedule_call") as schedule,
    ):
        coordinator._async_schedule_poll(dt_util.utcnow())
    assert schedule.call_count == int(expected)
    if expected:
        coordinator._needs_poll_method.assert_called_once_with(info, age)
        assert coordinator._last_service_info is info


async def test_timer_reads_unchanged_advertisements_and_stops(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A real timer and debouncer deliver repeated updates and stop on unload."""
    assert await async_setup_component(hass, "bluetooth", {})
    coordinator = make_coordinator(hass)
    info = MagicMock(time=0)
    processor = MagicMock()
    with (
        patch.object(coordinator_module, "async_address_present", return_value=True),
        patch.object(coordinator_module, "async_last_service_info", return_value=info),
        patch.object(
            coordinator_module, "monotonic_time_coarse", side_effect=monotonic
        ),
        patch(
            "homeassistant.components.bluetooth.active_update_processor.monotonic_time_coarse",
            side_effect=monotonic,
        ),
    ):
        cancel = coordinator.async_start()
        coordinator._processors.append(processor)
        for _ in range(2):
            freezer.tick(timedelta(seconds=60))
            async_fire_time_changed(hass, dt_util.utcnow())
            await hass.async_block_till_done(wait_background_tasks=True)
        assert coordinator._poll_method.await_count == 2
        assert processor.async_handle_update.call_count == 2
        cancel()
        assert coordinator._cancel_fallback is None
        freezer.tick(timedelta(seconds=120))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done(wait_background_tasks=True)
        assert coordinator._poll_method.await_count == 2


@pytest.mark.parametrize(("elapsed", "expected"), [(119, False), (120, True)])
async def test_timer_respects_configured_rate_limit(
    hass: HomeAssistant,
    elapsed: int,
    expected: bool,
) -> None:
    """A withheld final change can be read once the configured interval expires."""
    assert await async_setup_component(hass, "bluetooth", {})
    data = BMxBluetoothDeviceData()
    data.entry = MockConfigEntry(
        domain=DOMAIN, options={CONF_RATE_LIMIT_MODE: "always", CONF_RATE_LIMIT: 120}
    )
    coordinator = make_coordinator(hass)
    coordinator._last_poll = 100
    coordinator._needs_poll_method = data.poll_needed
    info = MagicMock(time=100)
    with (
        patch.object(coordinator_module, "async_address_present", return_value=True),
        patch.object(coordinator_module, "async_last_service_info", return_value=info),
        patch.object(
            coordinator_module, "monotonic_time_coarse", return_value=100 + elapsed
        ),
        patch.object(coordinator._debounced_poll, "async_schedule_call") as schedule,
    ):
        coordinator._async_schedule_poll(dt_util.utcnow())
    assert schedule.call_count == int(expected)


async def test_timer_publishes_passive_reading_after_startup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Publish cached telemetry after startup without a connectable device."""
    assert await async_setup_component(hass, "bluetooth", {})
    data = BMxBluetoothDeviceData()
    data.entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS)
    data.process_advertisement({11628: bytes.fromhex("b1e65b448775c27f1b9e78c09d53")})
    info = MagicMock(time=0, connectable=False)
    coordinator = make_coordinator(hass)

    async def poll(service_info: BluetoothServiceInfoBleak) -> SensorUpdate:
        assert service_info is info
        assert not service_info.connectable
        return await data.async_poll_sensors(None)

    coordinator._poll_method = AsyncMock(side_effect=poll)
    processor = MagicMock()
    with (
        patch.object(coordinator_module, "async_address_present", return_value=True),
        patch.object(coordinator_module, "async_last_service_info", return_value=info),
        patch.object(
            coordinator_module, "monotonic_time_coarse", side_effect=monotonic
        ),
        patch(
            "homeassistant.components.bluetooth.active_update_processor.monotonic_time_coarse",
            side_effect=monotonic,
        ),
        patch(
            "bmx_ble.protocol.establish_connection", new_callable=AsyncMock
        ) as connect,
    ):
        cancel = coordinator.async_start()
        coordinator._processors.append(processor)
        try:
            with patch.object(hass, "state", CoreState.starting):
                freezer.tick(timedelta(seconds=10))
                async_fire_time_changed(hass, dt_util.utcnow())
                await hass.async_block_till_done(wait_background_tasks=True)
            coordinator._poll_method.assert_not_awaited()
            processor.async_handle_update.assert_not_called()

            with patch.object(hass, "state", CoreState.running):
                freezer.tick(timedelta(seconds=10))
                async_fire_time_changed(hass, dt_util.utcnow())
                await hass.async_block_till_done(wait_background_tasks=True)
            coordinator._poll_method.assert_awaited_once_with(info)
            connect.assert_not_awaited()
            processor.async_handle_update.assert_called_once()
            update = processor.async_handle_update.call_args.args[0]
            values = {
                key.key: value.native_value
                for key, value in update.entity_values.items()
            }
            assert values["battery_voltage"] == 12.88
            assert values["battery_percent"] == 100
        finally:
            cancel()
