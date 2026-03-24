"""Transceiver abstraction for Easywave Core."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
import logging
import time

from easywave_home_control import RX11Device, RX11ErrorCode
import serial
import serial.tools.list_ports

from homeassistant.core import HomeAssistant

from .const import SUPPORTED_USB_IDS

_LOGGER = logging.getLogger(__name__)

_SERIAL_ERRORS: tuple[type[Exception], ...] = (
    serial.SerialException,
    serial.SerialTimeoutException,
)
_SERIAL_OR_OS_ERRORS: tuple[type[Exception], ...] = (
    *_SERIAL_ERRORS,
    OSError,
)


class RX11Transceiver:
    """ELDAT RX11 USB Transceiver implementation.

    Provides robust Connect/Disconnect, Hardware/Firmware version queries,
    and serial number tracking with device swap detection.

    Implements connection health monitoring and graceful disconnect/reconnect
    callbacks for notifying listeners of connection state changes.
    """

    # Connection health
    HEALTH_CHECK_INTERVAL = 30.0  # seconds

    def __init__(self, hass: HomeAssistant, device_path: str | None = None) -> None:
        """Initialize RX11 transceiver."""
        self.hass = hass
        self.device_path = device_path
        self.is_connected = False

        # USB device identification (for device swap detection)
        self.usb_serial_number: str | None = None

        # Version information
        self.hw_version: str | None = None
        self.fw_version: str | None = None

        # Connection tracking
        self._last_disconnect_time: float | None = None
        self._reconnect_attempts = 0

        # Device instance for protocol communication (async)
        self._device: RX11Device | None = None

        # Callbacks for connection state changes
        self._disconnect_callback: Callable[[], None] | None = None

        # Lock for async operations
        self._lock = asyncio.Lock()

        # Health check task
        self._health_check_task: asyncio.Task | None = None
        self._health_check_stopping = False

        # Disposed flag
        self._disposed = False

    def set_disconnect_callback(self, callback: Callable[[], None] | None) -> None:
        """Set callback to be called when disconnect/hardware error occurs."""
        self._disconnect_callback = callback

    def _notify_disconnect(self) -> None:
        """Notify disconnect callback if registered."""
        if self._disconnect_callback:
            try:
                self._disconnect_callback()
            except (OSError, RuntimeError) as err:
                _LOGGER.error("Error in disconnect callback: %s", err)

    async def connect(self) -> bool:
        """Connect to RX11 transceiver using RX11Device.

        1. Searches for RX11 device by VID/PID
        2. Creates RX11Device instance
        3. Connects and queries device info
        4. Starts health check

        Returns True if connected, False if device not found/error.
        """
        if self._disposed:
            return False

        async with self._lock:
            if self.is_connected:
                _LOGGER.debug("Already connected to RX11")
                return True

            try:
                # If specific device path provided, try it first
                if self.device_path:
                    if await self._try_connect_to_path(self.device_path):
                        await self._refresh_usb_identity()
                        return True

                # Configured path failed or not set — search by VID/PID
                port_info = await self.hass.async_add_executor_job(
                    self._find_usb_device
                )

                if port_info is None:
                    if self._reconnect_attempts == 0:
                        _LOGGER.warning("EASYWAVE device not found")
                    self.is_connected = False
                    return False

                device_path, serial_number = port_info
                self.device_path = device_path
                self.usb_serial_number = serial_number

                # Connect using RX11Device
                if not await self._try_connect_to_path(device_path):
                    if self._reconnect_attempts == 0:
                        _LOGGER.warning("Failed to connect to RX11 at %s", device_path)
                    self.is_connected = False
                    return False

                # Only reset the attempt counter after a successful connection
                self._reconnect_attempts = 0

            except _SERIAL_OR_OS_ERRORS as err:
                _LOGGER.debug("Cannot connect to RX11: %s", err)
                self.is_connected = False
                return False
            else:
                return True

    async def _try_connect_to_path(self, device_path: str) -> bool:
        """Try to connect to RX11 at a specific path using RX11Device.

        Follows the proven connect sequence:
        1. RX11Device() — creates RX11Device instance
        2. RX11Device.connect() — connects and starts serial handler thread
        3. Short settle time — let serial interface stabilize
        4. Query device info — verify connection is alive
        5. Start health check

        Returns True if connection successful, False otherwise.
        """
        try:
            # Create RX11Device instance directly
            self._device = RX11Device(port=device_path)

            if not self._device:
                return False

            # Connect to the device - this opens the serial connection and starts the handler thread
            connect_ok = await self._device.connect()
            if not connect_ok:
                _LOGGER.warning("Failed to connect RX11Device at %s", device_path)
                if self._device:
                    with contextlib.suppress(*_SERIAL_ERRORS, OSError):
                        await self._device.disconnect()
                    self._device = None
                return False

            self.is_connected = True
            self.device_path = device_path

            # Wait for serial interface to be fully ready (avoid race conditions)
            # This matches the HACS settle time that prevents startup errors
            await asyncio.sleep(1.5)

            # Fetch versions BEFORE starting any continuous receive loops
            versions_ok = await self._ensure_versions_fetched()
            if not versions_ok:
                _LOGGER.warning(
                    "Failed to query RX11 versions at %s; disconnecting",
                    device_path,
                )
                if self._device:
                    with contextlib.suppress(*_SERIAL_ERRORS, OSError):
                        await self._device.disconnect()
                    self._device = None
                self.is_connected = False
                self.device_path = None
                return False

            _LOGGER.info(
                "Connected to RX11 at %s (SN:%s, HW=%s, FW=%s)",
                device_path,
                self.usb_serial_number,
                self.hw_version or "unknown",
                self.fw_version or "unknown",
            )

            # Setup device callbacks for library-detected disconnects
            self._setup_device_callbacks()

            # Start health check
            await self._start_health_check()

        except _SERIAL_OR_OS_ERRORS as err:
            _LOGGER.warning("Error connecting to RX11 at %s: %s", device_path, err)
            if self._device:
                with contextlib.suppress(*_SERIAL_ERRORS, OSError):
                    await self._device.disconnect()
                self._device = None
            return False
        else:
            return True

    async def _refresh_usb_identity(self) -> None:
        """Read USB serial number from the connected port and update identity."""
        if not self.device_path:
            return
        try:

            def _scan():
                for port in serial.tools.list_ports.comports():
                    if port.device == self.device_path:
                        return port
                return None

            port = await self.hass.async_add_executor_job(_scan)
            if port:
                old_serial = self.usb_serial_number
                self.usb_serial_number = (
                    port.serial_number or self.usb_serial_number or "unknown"
                )
                if old_serial and old_serial != self.usb_serial_number:
                    _LOGGER.info(
                        "Device swap detected: %s -> %s",
                        old_serial,
                        self.usb_serial_number,
                    )
                    self.hw_version = None
                    self.fw_version = None
        except _SERIAL_OR_OS_ERRORS as e:
            _LOGGER.debug("Could not refresh USB identity: %s", e)

    async def disconnect(self) -> None:
        """Disconnect from the RX11 transceiver."""
        async with self._lock:
            # Stop health check
            await self._stop_health_check()

            # Clear device callbacks
            if self._device:
                self._device.set_disconnect_callback(None)
                self._device.set_reconnect_callback(None)

            # Disconnect device
            if self._device:
                with contextlib.suppress(*_SERIAL_ERRORS, OSError):
                    await self._device.disconnect()
                self._device = None

            self.is_connected = False
            self._last_disconnect_time = time.time()

    async def dispose(self) -> None:
        """Dispose of resources and clean up."""
        if self._disposed:
            return
        self._disposed = True
        await self.disconnect()

    async def _start_health_check(self) -> None:
        """Start health check task for device connection monitoring."""
        if self._health_check_task:
            return  # Already running

        self._health_check_stopping = False
        self._health_check_task = self.hass.async_create_background_task(
            self._health_check_loop(), "easywave health check"
        )

    async def _stop_health_check(self) -> None:
        """Stop health check task."""
        self._health_check_stopping = True
        if self._health_check_task:
            task = self._health_check_task
            self._health_check_task = None
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _health_check_loop(self) -> None:
        """Monitor device connection health using periodic ping requests."""
        try:
            consecutive_failures = 0
            max_consecutive_failures = 3

            while not self._health_check_stopping:
                try:
                    await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)

                    device = self._device  # Local reference for thread safety
                    if not self.is_connected or not device:
                        consecutive_failures = 0
                        continue

                    # Health check: Ping device to verify connection is active
                    connected = False
                    with contextlib.suppress(*_SERIAL_OR_OS_ERRORS):
                        connected = await device.ping_request()

                    if connected:
                        consecutive_failures = 0
                        _LOGGER.debug("Device health check passed")
                    else:
                        consecutive_failures += 1
                        _LOGGER.warning(
                            "Device health check failed (%d/%d)",
                            consecutive_failures,
                            max_consecutive_failures,
                        )

                        if consecutive_failures >= max_consecutive_failures:
                            _LOGGER.error(
                                "Device health check failed %d times, disconnecting",
                                max_consecutive_failures,
                            )
                            await self._handle_device_disconnect()
                            break

                except asyncio.CancelledError:
                    break
                except _SERIAL_OR_OS_ERRORS as e:
                    _LOGGER.debug("Error in health check: %s", e)
                    await asyncio.sleep(1.0)
        finally:
            self._health_check_task = None

    def _setup_device_callbacks(self) -> None:
        """Setup device disconnect/reconnect callbacks."""
        if self._device:
            # RxModule calls these when errors occur
            self._device.set_disconnect_callback(self._on_device_disconnect)
            self._device.set_reconnect_callback(self._on_device_reconnect)

    def _on_device_disconnect(self) -> None:
        """Handle device disconnect detected by RxModule."""
        _LOGGER.warning("Device disconnect detected by RxModule")

        def _schedule_disconnect_handling() -> None:
            """Schedule device disconnect handling on the event loop."""
            self.hass.async_create_task(self._handle_device_disconnect())

        # Callback may be invoked from the library's serial handler thread;
        # use call_soon_threadsafe to safely schedule onto the HA event loop.
        self.hass.loop.call_soon_threadsafe(_schedule_disconnect_handling)

    def _on_device_reconnect(self) -> None:
        """Handle device reconnect detected by RxModule."""
        _LOGGER.info("Device reconnect detected by RxModule")

    async def _handle_device_disconnect(self) -> None:
        """Handle device disconnect on the Home Assistant event loop."""
        async with self._lock:
            if not self.is_connected:
                return
            self.is_connected = False

        self._notify_disconnect()

        # Schedule full cleanup (stop health check, dispose device) outside
        # the lock to avoid deadlocks.
        async def _cleanup_disconnect() -> None:
            """Perform full cleanup after a device-initiated disconnect."""
            await self.disconnect()

        self.hass.async_create_background_task(
            _cleanup_disconnect(), "easywave device disconnect cleanup"
        )

    async def _ensure_versions_fetched(self) -> bool:
        """Ensure hardware and firmware versions are fetched.

        Uses RxModule query methods to get hardware and firmware versions.
        Includes retry with sleep between attempts.

        Returns True if at least one version was obtained successfully.
        """
        if not self._device:
            return False

        # Query hardware version with retry
        hw_version = None
        for attempt in range(3):
            try:
                result, hw_bytes = await self._device.query_hw_version(timeout=5.0)
                if result == RX11ErrorCode.SUCCESS:
                    # Find null terminator and decode
                    null_idx = hw_bytes.find(0)
                    if null_idx >= 0:
                        hw_bytes = hw_bytes[:null_idx]
                    hw_str = hw_bytes.decode("ascii", errors="ignore").strip()
                    if hw_str:
                        hw_version = hw_str
                        break
            except _SERIAL_OR_OS_ERRORS:
                pass

            if attempt < 2:
                wait_time = 0.5 * (attempt + 1)
                _LOGGER.debug(
                    "Hardware version query failed (attempt %d/3), retrying in %.1fs",
                    attempt + 1,
                    wait_time,
                )
                await asyncio.sleep(wait_time)

        # Query firmware version with retry
        fw_version = None
        for attempt in range(3):
            try:
                result, major, minor, incomplete = await self._device.query_fw_version(
                    timeout=5.0
                )
                if result == RX11ErrorCode.SUCCESS:
                    fw_version = f"{major}.{minor}"
                    if incomplete:
                        fw_version += " (incomplete)"
                    break
            except _SERIAL_OR_OS_ERRORS:
                pass

            if attempt < 2:
                wait_time = 0.5 * (attempt + 1)
                _LOGGER.debug(
                    "Firmware version query failed (attempt %d/3), retrying in %.1fs",
                    attempt + 1,
                    wait_time,
                )
                await asyncio.sleep(wait_time)

        self.hw_version = hw_version or "unknown"
        self.fw_version = fw_version or "unknown"

        if not hw_version and not fw_version:
            _LOGGER.warning("Version query failed")
            return False
        return True

    def _find_usb_device(self) -> tuple[str, str] | None:
        """Find EASYWAVE device by VID/PID.

        This is a blocking call and should only be executed in an executor.
        Searches through all supported device types.

        Returns: (device_path, serial_number) or None if not found
        """
        try:
            ports = list(serial.tools.list_ports.comports())
        except _SERIAL_OR_OS_ERRORS:
            _LOGGER.exception("Error while enumerating serial ports for EASYWAVE")
            return None

        for port in ports:
            if (port.vid, port.pid) in SUPPORTED_USB_IDS:
                # Test open/close
                if self._test_serial_port(port.device):
                    return (
                        port.device,
                        port.serial_number or "unknown",
                    )

        return None

    def _test_serial_port(self, port_path: str) -> bool:
        """Test if a serial port can be opened (blocking)."""
        try:
            test_port = serial.Serial(
                port=port_path,
                baudrate=115200,
                timeout=0.5,
            )
            test_port.close()
        except _SERIAL_ERRORS:
            return False
        else:
            return True

    async def reconnect(self) -> bool:
        """Reconnect to RX11 with delay and exponential backoff.

        Implements pattern from RxModule:
        - Adds delay if recently disconnected for device reset
        - Increments reconnect attempt counter
        - Searches for the device again if needed
        - Calls reconnect callback on success

        Returns:
            True if connection successful, False otherwise
        """
        if self._disposed:
            return False

        try:
            # Add delay if recently disconnected to allow device to reset
            if self._last_disconnect_time:
                time_since_disconnect = time.time() - self._last_disconnect_time
                if time_since_disconnect < 1.0:  # Less than 1 second
                    delay = 1.0 - time_since_disconnect
                    _LOGGER.debug("Waiting %.2fs for RX11 device to reset", delay)
                    await asyncio.sleep(delay)

            await self.disconnect()
            self._reconnect_attempts += 1

            if await self.connect():
                self._reconnect_attempts = 0
                return True
            if self._reconnect_attempts == 1:
                _LOGGER.debug(
                    "RX11 reconnect failed, retrying every %ds",
                    int(self.HEALTH_CHECK_INTERVAL),
                )

        except _SERIAL_ERRORS as err:
            _LOGGER.debug("Error during reconnect: %s", err)
            return False
        else:
            return False
