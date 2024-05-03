"""Tests for the Bluetooth integration scanners."""

import asyncio
from datetime import timedelta
import time
from unittest.mock import ANY, MagicMock, patch

from bleak import BleakError
from bleak.backends.scanner import AdvertisementDataCallback
from dbus_fast import InvalidMessageError
import pytest

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.const import (
    SCANNER_WATCHDOG_INTERVAL,
    SCANNER_WATCHDOG_TIMEOUT,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    async_setup_with_one_adapter,
    generate_advertisement_data,
    generate_ble_device,
    patch_bluetooth_time,
)

from tests.common import MockConfigEntry, async_fire_time_changed

# If the adapter is in a stuck state the following errors are raised:
NEED_RESET_ERRORS = [
    "org.bluez.Error.Failed",
    "org.bluez.Error.InProgress",
    "org.bluez.Error.NotReady",
    "not found",
]


async def test_config_entry_can_be_reloaded_when_stop_raises(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_bluetooth: None,
    macos_adapter: None,
) -> None:
    """Test we can reload if stopping the scanner raises."""
    entry = hass.config_entries.async_entries(bluetooth.DOMAIN)[0]
    assert entry.state is ConfigEntryState.LOADED

    with patch(
        "habluetooth.scanner.OriginalBleakScanner.stop",
        side_effect=BleakError,
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert "Error stopping scanner" in caplog.text


async def test_dbus_socket_missing_in_container(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, one_adapter: None
) -> None:
    """Test we handle dbus being missing in the container."""

    with (
        patch("habluetooth.scanner.is_docker_env", return_value=True),
        patch(
            "habluetooth.scanner.OriginalBleakScanner.start",
            side_effect=FileNotFoundError,
        ),
    ):
        await async_setup_with_one_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "/run/dbus" in caplog.text
    assert "docker" in caplog.text


async def test_dbus_socket_missing(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, one_adapter: None
) -> None:
    """Test we handle dbus being missing."""

    with (
        patch("habluetooth.scanner.is_docker_env", return_value=False),
        patch(
            "habluetooth.scanner.OriginalBleakScanner.start",
            side_effect=FileNotFoundError,
        ),
    ):
        await async_setup_with_one_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "DBus" in caplog.text
    assert "docker" not in caplog.text


async def test_dbus_broken_pipe_in_container(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, one_adapter: None
) -> None:
    """Test we handle dbus broken pipe in the container."""

    with (
        patch("habluetooth.scanner.is_docker_env", return_value=True),
        patch(
            "habluetooth.scanner.OriginalBleakScanner.start",
            side_effect=BrokenPipeError,
        ),
    ):
        await async_setup_with_one_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "dbus" in caplog.text
    assert "restarting" in caplog.text
    assert "container" in caplog.text


async def test_dbus_broken_pipe(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, one_adapter: None
) -> None:
    """Test we handle dbus broken pipe."""

    with (
        patch("habluetooth.scanner.is_docker_env", return_value=False),
        patch(
            "habluetooth.scanner.OriginalBleakScanner.start",
            side_effect=BrokenPipeError,
        ),
    ):
        await async_setup_with_one_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "DBus" in caplog.text
    assert "restarting" in caplog.text
    assert "container" not in caplog.text


async def test_invalid_dbus_message(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, one_adapter: None
) -> None:
    """Test we handle invalid dbus message."""

    with patch(
        "habluetooth.scanner.OriginalBleakScanner.start",
        side_effect=InvalidMessageError,
    ):
        await async_setup_with_one_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "dbus" in caplog.text


@pytest.mark.parametrize("error", NEED_RESET_ERRORS)
async def test_adapter_needs_reset_at_start(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, one_adapter: None, error: str
) -> None:
    """Test we cycle the adapter when it needs a restart."""

    with (
        patch(
            "habluetooth.scanner.OriginalBleakScanner.start",
            side_effect=[BleakError(error), BleakError(error), None],
        ),
        patch(
            "habluetooth.util.recover_adapter", return_value=True
        ) as mock_recover_adapter,
    ):
        await async_setup_with_one_adapter(hass)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_recover_adapter.mock_calls) == 1

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()


async def test_recovery_from_dbus_restart(
    hass: HomeAssistant, one_adapter: None
) -> None:
    """Test we can recover when DBus gets restarted out from under us."""

    called_start = 0
    called_stop = 0
    _callback = None
    mock_discovered = []

    class MockBleakScanner:
        def __init__(self, detection_callback, *args, **kwargs):
            nonlocal _callback
            _callback = detection_callback

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

    with patch(
        "habluetooth.scanner.OriginalBleakScanner",
        MockBleakScanner,
    ):
        await async_setup_with_one_adapter(hass)

        assert called_start == 1

        start_time_monotonic = time.monotonic()
        mock_discovered = [MagicMock()]

        # Ensure we don't restart the scanner if we don't need to
        with patch_bluetooth_time(
            start_time_monotonic + 10,
        ):
            async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
            await hass.async_block_till_done()

        assert called_start == 1

        # Fire a callback to reset the timer
        with patch_bluetooth_time(
            start_time_monotonic,
        ):
            _callback(
                generate_ble_device("44:44:33:11:23:42", "any_name"),
                generate_advertisement_data(local_name="any_name"),
            )

        # Ensure we don't restart the scanner if we don't need to
        with patch_bluetooth_time(
            start_time_monotonic + 20,
        ):
            async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
            await hass.async_block_till_done()

        assert called_start == 1

        # We hit the timer, so we restart the scanner
        with patch_bluetooth_time(
            start_time_monotonic + SCANNER_WATCHDOG_TIMEOUT + 20,
        ):
            async_fire_time_changed(
                hass,
                dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL + timedelta(seconds=20),
            )
            await hass.async_block_till_done()

        assert called_start == 2


async def test_adapter_recovery(hass: HomeAssistant, one_adapter: None) -> None:
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
    start_time_monotonic = time.monotonic()

    with (
        patch_bluetooth_time(
            start_time_monotonic,
        ),
        patch(
            "habluetooth.scanner.OriginalBleakScanner",
            return_value=scanner,
        ),
    ):
        await async_setup_with_one_adapter(hass)

        assert called_start == 1

        mock_discovered = [MagicMock()]

        # Ensure we don't restart the scanner if we don't need to
        with patch_bluetooth_time(
            start_time_monotonic + 10,
        ):
            async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
            await hass.async_block_till_done()

        assert called_start == 1

        # Ensure we don't restart the scanner if we don't need to
        with patch_bluetooth_time(
            start_time_monotonic + 20,
        ):
            async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
            await hass.async_block_till_done()

        assert called_start == 1

        # We hit the timer with no detections, so we reset the adapter and restart the scanner
        with (
            patch_bluetooth_time(
                start_time_monotonic
                + SCANNER_WATCHDOG_TIMEOUT
                + SCANNER_WATCHDOG_INTERVAL.total_seconds(),
            ),
            patch(
                "habluetooth.util.recover_adapter", return_value=True
            ) as mock_recover_adapter,
        ):
            async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
            await hass.async_block_till_done()

        assert len(mock_recover_adapter.mock_calls) == 1
        assert called_start == 2


async def test_adapter_scanner_fails_to_start_first_time(
    hass: HomeAssistant, one_adapter: None
) -> None:
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
    start_time_monotonic = time.monotonic()

    with (
        patch_bluetooth_time(
            start_time_monotonic,
        ),
        patch(
            "habluetooth.scanner.OriginalBleakScanner",
            return_value=scanner,
        ),
    ):
        await async_setup_with_one_adapter(hass)

        assert called_start == 1

        mock_discovered = [MagicMock()]

        # Ensure we don't restart the scanner if we don't need to
        with patch_bluetooth_time(
            start_time_monotonic + 10,
        ):
            async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
            await hass.async_block_till_done()

        assert called_start == 1

        # Ensure we don't restart the scanner if we don't need to
        with patch_bluetooth_time(
            start_time_monotonic + 20,
        ):
            async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
            await hass.async_block_till_done()

        assert called_start == 1

        # We hit the timer with no detections, so we reset the adapter and restart the scanner
        with (
            patch_bluetooth_time(
                start_time_monotonic
                + SCANNER_WATCHDOG_TIMEOUT
                + SCANNER_WATCHDOG_INTERVAL.total_seconds(),
            ),
            patch(
                "habluetooth.util.recover_adapter", return_value=True
            ) as mock_recover_adapter,
        ):
            async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
            await hass.async_block_till_done()

        assert len(mock_recover_adapter.mock_calls) == 1
        assert called_start == 4

        now_monotonic = time.monotonic()
        # We hit the timer again the previous start call failed, make sure
        # we try again
        with (
            patch_bluetooth_time(
                now_monotonic
                + SCANNER_WATCHDOG_TIMEOUT * 2
                + SCANNER_WATCHDOG_INTERVAL.total_seconds(),
            ),
            patch(
                "habluetooth.util.recover_adapter", return_value=True
            ) as mock_recover_adapter,
        ):
            async_fire_time_changed(hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL)
            await hass.async_block_till_done()

        assert len(mock_recover_adapter.mock_calls) == 1
        assert called_start == 5


async def test_adapter_fails_to_start_and_takes_a_bit_to_init(
    hass: HomeAssistant, one_adapter: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we can recover the adapter at startup and we wait for Dbus to init."""
    assert await async_setup_component(hass, "logger", {})
    await hass.services.async_call(
        "logger",
        "set_level",
        {"homeassistant.components.bluetooth": "DEBUG"},
        blocking=True,
    )
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
                raise BleakError("org.freedesktop.DBus.Error.UnknownObject")
            if called_start == 2:
                raise BleakError("org.bluez.Error.InProgress")
            if called_start == 3:
                raise BleakError("org.bluez.Error.InProgress")

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
    start_time_monotonic = time.monotonic()

    with (
        patch(
            "habluetooth.scanner.ADAPTER_INIT_TIME",
            0,
        ),
        patch_bluetooth_time(
            start_time_monotonic,
        ),
        patch(
            "habluetooth.scanner.OriginalBleakScanner",
            return_value=scanner,
        ),
        patch(
            "habluetooth.util.recover_adapter", return_value=True
        ) as mock_recover_adapter,
    ):
        await async_setup_with_one_adapter(hass)

        assert called_start == 4

    assert len(mock_recover_adapter.mock_calls) == 1
    assert "Waiting for adapter to initialize" in caplog.text


async def test_restart_takes_longer_than_watchdog_time(
    hass: HomeAssistant, one_adapter: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we do not try to recover the adapter again if the restart is still in progress."""

    release_start_event = asyncio.Event()
    called_start = 0

    class MockBleakScanner:
        async def start(self, *args, **kwargs):
            """Mock Start."""
            nonlocal called_start
            called_start += 1
            if called_start == 1:
                return
            await release_start_event.wait()

        async def stop(self, *args, **kwargs):
            """Mock Start."""

        @property
        def discovered_devices(self):
            """Mock discovered_devices."""
            return []

        def register_detection_callback(self, callback: AdvertisementDataCallback):
            """Mock Register Detection Callback."""

    scanner = MockBleakScanner()
    start_time_monotonic = time.monotonic()

    with (
        patch(
            "habluetooth.scanner.ADAPTER_INIT_TIME",
            0,
        ),
        patch_bluetooth_time(
            start_time_monotonic,
        ),
        patch(
            "habluetooth.scanner.OriginalBleakScanner",
            return_value=scanner,
        ),
        patch("habluetooth.util.recover_adapter", return_value=True),
    ):
        await async_setup_with_one_adapter(hass)

        assert called_start == 1

        # Now force a recover adapter 2x
        for _ in range(2):
            with patch_bluetooth_time(
                start_time_monotonic
                + SCANNER_WATCHDOG_TIMEOUT
                + SCANNER_WATCHDOG_INTERVAL.total_seconds(),
            ):
                async_fire_time_changed(
                    hass, dt_util.utcnow() + SCANNER_WATCHDOG_INTERVAL
                )
                await asyncio.sleep(0)

        # Now release the start event
        release_start_event.set()
        await hass.async_block_till_done()

    assert "already restarting" in caplog.text


@pytest.mark.skipif("platform.system() != 'Darwin'")
async def test_setup_and_stop_macos(
    hass: HomeAssistant, mock_bleak_scanner_start: MagicMock, macos_adapter: None
) -> None:
    """Test we enable use_bdaddr on MacOS."""
    entry = MockConfigEntry(
        domain=bluetooth.DOMAIN,
        data={},
        unique_id="00:00:00:00:00:00",
    )
    entry.add_to_hass(hass)
    init_kwargs = None

    class MockBleakScanner:
        def __init__(self, *args, **kwargs):
            """Init the scanner."""
            nonlocal init_kwargs
            init_kwargs = kwargs

        async def start(self, *args, **kwargs):
            """Start the scanner."""

        async def stop(self, *args, **kwargs):
            """Stop the scanner."""

        def register_detection_callback(self, *args, **kwargs):
            """Register a callback."""

    with patch(
        "habluetooth.scanner.OriginalBleakScanner",
        MockBleakScanner,
    ):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert init_kwargs == {
        "detection_callback": ANY,
        "scanning_mode": "active",
        "cb": {"use_bdaddr": True},
    }
