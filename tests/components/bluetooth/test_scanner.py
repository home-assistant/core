"""Tests for the Bluetooth integration scanners."""
from unittest.mock import MagicMock, patch

from bleak import BleakError
from bleak.backends.scanner import (
    AdvertisementData,
    AdvertisementDataCallback,
    BLEDevice,
)
from dbus_next import InvalidMessageError
import pytest

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.const import (
    SCANNER_WATCHDOG_INTERVAL,
    SCANNER_WATCHDOG_TIMEOUT,
)
from homeassistant.components.bluetooth.scanner import NEED_RESET_ERRORS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.util import dt as dt_util

from . import _get_manager, async_setup_with_one_adapter

from tests.common import async_fire_time_changed


async def test_config_entry_can_be_reloaded_when_stop_raises(
    hass, caplog, enable_bluetooth, macos_adapter
):
    """Test we can reload if stopping the scanner raises."""
    entry = hass.config_entries.async_entries(bluetooth.DOMAIN)[0]
    assert entry.state == ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.stop",
        side_effect=BleakError,
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED
    assert "Error stopping scanner" in caplog.text


async def test_dbus_socket_missing_in_container(hass, caplog, one_adapter):
    """Test we handle dbus being missing in the container."""

    with patch(
        "homeassistant.components.bluetooth.scanner.is_docker_env", return_value=True
    ), patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=FileNotFoundError,
    ):
        await async_setup_with_one_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "/run/dbus" in caplog.text
    assert "docker" in caplog.text


async def test_dbus_socket_missing(hass, caplog, one_adapter):
    """Test we handle dbus being missing."""

    with patch(
        "homeassistant.components.bluetooth.scanner.is_docker_env", return_value=False
    ), patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=FileNotFoundError,
    ):
        await async_setup_with_one_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "DBus" in caplog.text
    assert "docker" not in caplog.text


async def test_dbus_broken_pipe_in_container(hass, caplog, one_adapter):
    """Test we handle dbus broken pipe in the container."""

    with patch(
        "homeassistant.components.bluetooth.scanner.is_docker_env", return_value=True
    ), patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=BrokenPipeError,
    ):
        await async_setup_with_one_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "dbus" in caplog.text
    assert "restarting" in caplog.text
    assert "container" in caplog.text


async def test_dbus_broken_pipe(hass, caplog, one_adapter):
    """Test we handle dbus broken pipe."""

    with patch(
        "homeassistant.components.bluetooth.scanner.is_docker_env", return_value=False
    ), patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=BrokenPipeError,
    ):
        await async_setup_with_one_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "DBus" in caplog.text
    assert "restarting" in caplog.text
    assert "container" not in caplog.text


async def test_invalid_dbus_message(hass, caplog, one_adapter):
    """Test we handle invalid dbus message."""

    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=InvalidMessageError,
    ):
        await async_setup_with_one_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "dbus" in caplog.text


@pytest.mark.parametrize("error", NEED_RESET_ERRORS)
async def test_adapter_needs_reset_at_start(hass, caplog, one_adapter, error):
    """Test we cycle the adapter when it needs a restart."""

    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=[BleakError(error), None],
    ), patch(
        "homeassistant.components.bluetooth.util.recover_adapter", return_value=True
    ) as mock_recover_adapter:
        await async_setup_with_one_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_recover_adapter.mock_calls) == 1

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()


async def test_recovery_from_dbus_restart(hass, one_adapter):
    """Test we can recover when DBus gets restarted out from under us."""

    called_start = 0
    called_stop = 0
    _callback = None
    mock_discovered = []

    class MockBleakScanner:
        async def start(self, *args, **kwargs):
            """Mock Start."""
            nonlocal called_start
            called_start += 1

        async def stop(self, *args, **kwargs):
            """Mock Start."""
            nonlocal called_stop
            called_stop += 1

        @property
        def discovered_devices(self):
            """Mock discovered_devices."""
            nonlocal mock_discovered
            return mock_discovered

        def register_detection_callback(self, callback: AdvertisementDataCallback):
            """Mock Register Detection Callback."""
            nonlocal _callback
            _callback = callback

    scanner = MockBleakScanner()

    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner",
        return_value=scanner,
    ):
        await async_setup_with_one_adapter(hass)

        assert called_start == 1

    start_time_monotonic = 1000
    scanner = _get_manager()
    mock_discovered = [MagicMock()]

    # Ensure we don't restart the scanner if we don't need to
    with patch(
        "homeassistant.components.bluetooth.scanner.MONOTONIC_TIME",
        return_value=start_time_monotonic + 10,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
        await hass.async_block_till_done()

    assert called_start == 1

    # Fire a callback to reset the timer
    with patch(
        "homeassistant.components.bluetooth.scanner.MONOTONIC_TIME",
        return_value=start_time_monotonic,
    ):
        _callback(
            BLEDevice("44:44:33:11:23:42", "any_name"),
            AdvertisementData(local_name="any_name"),
        )

    # Ensure we don't restart the scanner if we don't need to
    with patch(
        "homeassistant.components.bluetooth.scanner.MONOTONIC_TIME",
        return_value=start_time_monotonic + 20,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
        await hass.async_block_till_done()

    assert called_start == 1

    # We hit the timer, so we restart the scanner
    with patch(
        "homeassistant.components.bluetooth.scanner.MONOTONIC_TIME",
        return_value=start_time_monotonic + SCANNER_WATCHDOG_TIMEOUT,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
        await hass.async_block_till_done()

    assert called_start == 2


async def test_adapter_recovery(hass, one_adapter):
    """Test we can recover when the adapter stops responding."""

    called_start = 0
    called_stop = 0
    _callback = None
    mock_discovered = []

    class MockBleakScanner:
        async def start(self, *args, **kwargs):
            """Mock Start."""
            nonlocal called_start
            called_start += 1

        async def stop(self, *args, **kwargs):
            """Mock Start."""
            nonlocal called_stop
            called_stop += 1

        @property
        def discovered_devices(self):
            """Mock discovered_devices."""
            nonlocal mock_discovered
            return mock_discovered

        def register_detection_callback(self, callback: AdvertisementDataCallback):
            """Mock Register Detection Callback."""
            nonlocal _callback
            _callback = callback

    scanner = MockBleakScanner()
    start_time_monotonic = 1000

    with patch(
        "homeassistant.components.bluetooth.scanner.MONOTONIC_TIME",
        return_value=start_time_monotonic,
    ), patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner",
        return_value=scanner,
    ):
        await async_setup_with_one_adapter(hass)

        assert called_start == 1

    scanner = _get_manager()
    mock_discovered = [MagicMock()]

    # Ensure we don't restart the scanner if we don't need to
    with patch(
        "homeassistant.components.bluetooth.scanner.MONOTONIC_TIME",
        return_value=start_time_monotonic + 10,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
        await hass.async_block_till_done()

    assert called_start == 1

    # Ensure we don't restart the scanner if we don't need to
    with patch(
        "homeassistant.components.bluetooth.scanner.MONOTONIC_TIME",
        return_value=start_time_monotonic + 20,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
        await hass.async_block_till_done()

    assert called_start == 1

    # We hit the timer with no detections, so we reset the adapter and restart the scanner
    with patch(
        "homeassistant.components.bluetooth.scanner.MONOTONIC_TIME",
        return_value=start_time_monotonic
        + SCANNER_WATCHDOG_TIMEOUT
        + SCANNER_WATCHDOG_INTERVAL.total_seconds(),
    ), patch(
        "homeassistant.components.bluetooth.util.recover_adapter", return_value=True
    ) as mock_recover_adapter:
        async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
        await hass.async_block_till_done()

    assert len(mock_recover_adapter.mock_calls) == 1
    assert called_start == 2


async def test_adapter_scanner_fails_to_start_first_time(hass, one_adapter):
    """Test we can recover when the adapter stops responding and the first recovery fails."""

    called_start = 0
    called_stop = 0
    _callback = None
    mock_discovered = []

    class MockBleakScanner:
        async def start(self, *args, **kwargs):
            """Mock Start."""
            nonlocal called_start
            called_start += 1
            if called_start == 1:
                return  # Start ok the first time
            if called_start < 4:
                raise BleakError("Failed to start")

        async def stop(self, *args, **kwargs):
            """Mock Start."""
            nonlocal called_stop
            called_stop += 1

        @property
        def discovered_devices(self):
            """Mock discovered_devices."""
            nonlocal mock_discovered
            return mock_discovered

        def register_detection_callback(self, callback: AdvertisementDataCallback):
            """Mock Register Detection Callback."""
            nonlocal _callback
            _callback = callback

    scanner = MockBleakScanner()
    start_time_monotonic = 1000

    with patch(
        "homeassistant.components.bluetooth.scanner.MONOTONIC_TIME",
        return_value=start_time_monotonic,
    ), patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner",
        return_value=scanner,
    ):
        await async_setup_with_one_adapter(hass)

        assert called_start == 1

    scanner = _get_manager()
    mock_discovered = [MagicMock()]

    # Ensure we don't restart the scanner if we don't need to
    with patch(
        "homeassistant.components.bluetooth.scanner.MONOTONIC_TIME",
        return_value=start_time_monotonic + 10,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
        await hass.async_block_till_done()

    assert called_start == 1

    # Ensure we don't restart the scanner if we don't need to
    with patch(
        "homeassistant.components.bluetooth.scanner.MONOTONIC_TIME",
        return_value=start_time_monotonic + 20,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
        await hass.async_block_till_done()

    assert called_start == 1

    # We hit the timer with no detections, so we reset the adapter and restart the scanner
    with patch(
        "homeassistant.components.bluetooth.scanner.MONOTONIC_TIME",
        return_value=start_time_monotonic
        + SCANNER_WATCHDOG_TIMEOUT
        + SCANNER_WATCHDOG_INTERVAL.total_seconds(),
    ), patch(
        "homeassistant.components.bluetooth.util.recover_adapter", return_value=True
    ) as mock_recover_adapter:
        async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
        await hass.async_block_till_done()

    assert len(mock_recover_adapter.mock_calls) == 1
    assert called_start == 3

    # We hit the timer again the previous start call failed, make sure
    # we try again
    with patch(
        "homeassistant.components.bluetooth.scanner.MONOTONIC_TIME",
        return_value=start_time_monotonic
        + SCANNER_WATCHDOG_TIMEOUT
        + SCANNER_WATCHDOG_INTERVAL.total_seconds(),
    ), patch(
        "homeassistant.components.bluetooth.util.recover_adapter", return_value=True
    ) as mock_recover_adapter:
        async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
        await hass.async_block_till_done()

    assert len(mock_recover_adapter.mock_calls) == 1
    assert called_start == 4


async def test_adapter_fails_to_start_and_takes_a_bit_to_init(
    hass, one_adapter, caplog
):
    """Test we can recover the adapter at startup and we wait for Dbus to init."""

    called_start = 0
    called_stop = 0
    _callback = None
    mock_discovered = []

    class MockBleakScanner:
        async def start(self, *args, **kwargs):
            """Mock Start."""
            nonlocal called_start
            called_start += 1
            if called_start == 1:
                raise BleakError("org.bluez.Error.InProgress")
            if called_start == 2:
                raise BleakError("org.freedesktop.DBus.Error.UnknownObject")

        async def stop(self, *args, **kwargs):
            """Mock Start."""
            nonlocal called_stop
            called_stop += 1

        @property
        def discovered_devices(self):
            """Mock discovered_devices."""
            nonlocal mock_discovered
            return mock_discovered

        def register_detection_callback(self, callback: AdvertisementDataCallback):
            """Mock Register Detection Callback."""
            nonlocal _callback
            _callback = callback

    scanner = MockBleakScanner()
    start_time_monotonic = 1000

    with patch(
        "homeassistant.components.bluetooth.scanner.ADAPTER_INIT_TIME",
        0,
    ), patch(
        "homeassistant.components.bluetooth.scanner.MONOTONIC_TIME",
        return_value=start_time_monotonic,
    ), patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner",
        return_value=scanner,
    ), patch(
        "homeassistant.components.bluetooth.util.recover_adapter", return_value=True
    ) as mock_recover_adapter:
        await async_setup_with_one_adapter(hass)

        assert called_start == 3

    assert len(mock_recover_adapter.mock_calls) == 1
    assert "Waiting for adapter to initialize" in caplog.text
