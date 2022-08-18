"""Tests for the Bluetooth integration scanners."""
from unittest.mock import MagicMock, patch

from bleak import BleakError
from bleak.backends.scanner import (
    AdvertisementData,
    AdvertisementDataCallback,
    BLEDevice,
)
from dbus_next import InvalidMessageError

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.const import (
    CONF_ADAPTER,
    SCANNER_WATCHDOG_INTERVAL,
    SCANNER_WATCHDOG_TIMEOUT,
    UNIX_DEFAULT_BLUETOOTH_ADAPTER,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import _get_manager

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_config_entry_can_be_reloaded_when_stop_raises(
    hass, caplog, enable_bluetooth
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


async def test_changing_the_adapter_at_runtime(hass):
    """Test we can change the adapter at runtime."""
    entry = MockConfigEntry(
        domain=bluetooth.DOMAIN,
        data={},
        options={CONF_ADAPTER: UNIX_DEFAULT_BLUETOOTH_ADAPTER},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start"
    ), patch("homeassistant.components.bluetooth.scanner.OriginalBleakScanner.stop"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entry.options = {CONF_ADAPTER: "hci1"}

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()


async def test_dbus_socket_missing_in_container(hass, caplog):
    """Test we handle dbus being missing in the container."""

    with patch(
        "homeassistant.components.bluetooth.scanner.is_docker_env", return_value=True
    ), patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=FileNotFoundError,
    ):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "/run/dbus" in caplog.text
    assert "docker" in caplog.text


async def test_dbus_socket_missing(hass, caplog):
    """Test we handle dbus being missing."""

    with patch(
        "homeassistant.components.bluetooth.scanner.is_docker_env", return_value=False
    ), patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=FileNotFoundError,
    ):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "DBus" in caplog.text
    assert "docker" not in caplog.text


async def test_dbus_broken_pipe_in_container(hass, caplog):
    """Test we handle dbus broken pipe in the container."""

    with patch(
        "homeassistant.components.bluetooth.scanner.is_docker_env", return_value=True
    ), patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=BrokenPipeError,
    ):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "dbus" in caplog.text
    assert "restarting" in caplog.text
    assert "container" in caplog.text


async def test_dbus_broken_pipe(hass, caplog):
    """Test we handle dbus broken pipe."""

    with patch(
        "homeassistant.components.bluetooth.scanner.is_docker_env", return_value=False
    ), patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=BrokenPipeError,
    ):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "DBus" in caplog.text
    assert "restarting" in caplog.text
    assert "container" not in caplog.text


async def test_invalid_dbus_message(hass, caplog):
    """Test we handle invalid dbus message."""

    with patch(
        "homeassistant.components.bluetooth.scanner.OriginalBleakScanner.start",
        side_effect=InvalidMessageError,
    ):
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert "dbus" in caplog.text


async def test_recovery_from_dbus_restart(hass):
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
        assert await async_setup_component(
            hass, bluetooth.DOMAIN, {bluetooth.DOMAIN: {}}
        )
        await hass.async_block_till_done()
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
