"""Transceiver abstraction for Easywave Core."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
import logging
import time

import serial
import serial.tools.list_ports

from homeassistant.core import HomeAssistant

from .const import SUPPORTED_USB_IDS
from .rx_module import _SERIAL_ERRORS, ErrorCode, RxModule

_LOGGER = logging.getLogger(__name__)

_SERIAL_VALUE_ERRORS: tuple[type[Exception], ...] = (*_SERIAL_ERRORS, ValueError)


class RX11Transceiver:
    """ELDAT RX11 USB Transceiver implementation.

    Provides robust Connect/Disconnect, Hardware/Firmware version queries,
    and serial number tracking with device swap detection.

    Implements connection health monitoring and graceful disconnect/reconnect
    callbacks for notifying listeners of connection state changes.

    Pattern based on github.com/eldateas/HomeAssistant-Integration
    """

    # Serial connection parameters
    BAUDRATE = 115200

    # Connection health
    HEALTH_CHECK_INTERVAL = 30.0  # seconds

    def __init__(self, hass: HomeAssistant, device_path: str | None = None) -> None:
        """Initialize RX11 transceiver."""
        self.hass = hass
        self.device_path = device_path
        self.is_connected = False

        # USB device identification (for device swap detection)
        self.usb_serial_number: str | None = None
        self.usb_vid: int | None = None
        self.usb_pid: int | None = None

        # Version information
        self.hw_version: str | None = None
        self.fw_version: str | None = None

        # Connection tracking
        self._last_disconnect_time: float | None = None
        self._hardware_error = False
        self._reconnect_attempts = 0

        # RxModule instance for protocol communication
        self._rxmodule: RxModule | None = None

        # Callbacks for connection state changes
        self._disconnect_callback: Callable[[], None] | None = None

        # Lock for async operations
        self._lock = asyncio.Lock()

        # Health check task
        self._health_check_task: asyncio.Task | None = None
        self._health_check_stopping = False

        # Disposed flag
        self._disposed = False

    # ═══════════════════════════════════════════════════════════════════════════════
    # CALLBACK MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════════════════════
    # CONNECTION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════════

    async def connect(self) -> bool:
        """Connect to RX11 transceiver using RxModule protocol.

        1. Searches for RX11 device by VID/PID
        2. Creates RxModule instance
        3. Connects and starts serial handler thread
        4. Waits for startup tolerance to expire
        5. Queries hardware/firmware versions
        6. Starts health check

        Returns True if connected, False if device not found/error.
        """
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
                    self._hardware_error = True
                    return False

                device_path, serial_number, vid, pid = port_info
                self.device_path = device_path
                self.usb_serial_number = serial_number
                self.usb_vid = vid
                self.usb_pid = pid
                self._reconnect_attempts = 0
                self._hardware_error = False

                # Connect using RxModule (replaces old serial connection logic)
                if not await self._try_connect_to_path(device_path):
                    if self._reconnect_attempts == 0:
                        _LOGGER.warning("Failed to connect to RX11 at %s", device_path)
                    self.is_connected = False
                    self._hardware_error = True
                    return False

            except _SERIAL_ERRORS as err:
                _LOGGER.debug("Cannot connect to RX11: %s", err)
                self.is_connected = False
                self._hardware_error = True
                return False
            else:
                return True

    async def _try_connect_to_path(self, device_path: str) -> bool:
        """Try to connect to RX11 at a specific path using RxModule protocol.

        Follows the proven connect sequence:
        1. RxModule.connect() — opens serial, drains buffer, starts handler thread
        2. Short settle time — let serial interface stabilize
        3. flush_serial_buffer() — remove any remaining stale data
        4. Query versions with retry — verify connection is alive
        5. Start health check

        Returns True if connection successful, False otherwise.
        """
        try:
            # Create RxModule instance
            self._rxmodule = RxModule(port=device_path, baudrate=self.BAUDRATE)

            # Connect RxModule (blocking - runs in executor)
            connect_success = await self.hass.async_add_executor_job(
                self._rxmodule.connect
            )

            if not connect_success:
                if self._rxmodule:
                    with contextlib.suppress(*_SERIAL_ERRORS):
                        await self.hass.async_add_executor_job(self._rxmodule.dispose)
                    self._rxmodule = None
                return False

            self.is_connected = True
            self.device_path = device_path

            # Register disconnect callback so the serial handler thread
            # can notify us immediately when USB is unplugged.
            self._rxmodule.set_disconnect_callback(self._on_rxmodule_disconnect)

            # Wait for serial interface to be fully ready (avoid race conditions)
            # This matches the HACS settle time that prevents startup errors
            await asyncio.sleep(0.8)

            # Final buffer flush right before version queries to remove any
            # stale data that arrived during the settle window
            await self.hass.async_add_executor_job(self._rxmodule.flush_serial_buffer)

            # Fetch versions BEFORE starting any continuous receive loops
            # Both queries use synchronous request/response matching
            await self._ensure_versions_fetched()

            _LOGGER.info(
                "Connected to RX11 at %s (SN:%s, HW=%s, FW=%s)",
                device_path,
                self.usb_serial_number,
                self.hw_version or "unknown",
                self.fw_version or "unknown",
            )

            # Start health check
            await self._start_health_check()

        except _SERIAL_ERRORS as err:
            _LOGGER.warning("Error connecting to RX11 at %s: %s", device_path, err)
            if self._rxmodule:
                with contextlib.suppress(*_SERIAL_ERRORS):
                    await self.hass.async_add_executor_job(self._rxmodule.dispose)
                self._rxmodule = None
            return False
        else:
            return True

    async def _refresh_usb_identity(self) -> None:
        """Read actual USB serial/VID/PID from the connected port and update identity."""
        if not self.device_path:
            return
        try:

            def _scan():
                for port in serial.tools.list_ports.comports():
                    if port.device == self.device_path:
                        return port
                return None

            port = await self.hass.async_add_executor_job(_scan)
            if port and port.vid and port.pid:
                old_serial = self.usb_serial_number
                self.usb_serial_number = port.serial_number
                self.usb_vid = port.vid
                self.usb_pid = port.pid
                if old_serial and old_serial != self.usb_serial_number:
                    _LOGGER.info(
                        "Device swap detected: %s -> %s",
                        old_serial,
                        self.usb_serial_number,
                    )
                    self.hw_version = None
                    self.fw_version = None
        except _SERIAL_ERRORS as e:
            _LOGGER.debug("Could not refresh USB identity: %s", e)

    async def disconnect(self) -> None:
        """Disconnect from the RX11 transceiver."""
        if self._disposed:
            return

        async with self._lock:
            # Stop health check
            await self._stop_health_check()

            # Disconnect RxModule
            if self._rxmodule:
                with contextlib.suppress(*_SERIAL_ERRORS):
                    await self.hass.async_add_executor_job(self._rxmodule.dispose)
                self._rxmodule = None

            self.is_connected = False
            self._last_disconnect_time = time.time()

    async def dispose(self) -> None:
        """Dispose of resources and clean up."""
        if self._disposed:
            return
        self._disposed = True
        await self.disconnect()

    # ═══════════════════════════════════════════════════════════════════════════════
    # HEALTH CHECK
    # ═══════════════════════════════════════════════════════════════════════════════

    async def _start_health_check(self) -> None:
        """Start health check task for RxModule connection monitoring."""
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
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except TimeoutError:
                _LOGGER.warning("Health check task did not complete within timeout")
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            finally:
                if self._health_check_task is task:
                    self._health_check_task = None

    async def _health_check_loop(self) -> None:
        """Monitor RxModule connection health.

        Checks if module is still in good state. If connection fails,
        marks as disconnected.
        """
        while not self._health_check_stopping:
            try:
                await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)

                if not self.is_connected or not self._rxmodule:
                    continue

                # Check if RxModule is still healthy
                if not self._rxmodule.is_connected or not self._rxmodule.state_good:
                    _LOGGER.warning("RxModule health check failed")
                    self.is_connected = False
                    self._notify_disconnect()
                    break

            except asyncio.CancelledError:
                break
            except _SERIAL_ERRORS as e:
                _LOGGER.debug("Error in health check: %s", e)
                await asyncio.sleep(1.0)

    def _on_rxmodule_disconnect(self) -> None:
        """Called from RxModule serial handler thread on USB disconnect."""
        if not self.is_connected:
            return
        self.is_connected = False
        self._hardware_error = True
        self._notify_disconnect()

    # ═══════════════════════════════════════════════════════════════════════════════
    # VERSION QUERIES
    # ═══════════════════════════════════════════════════════════════════════════════

    async def _ensure_versions_fetched(self) -> bool:
        """Ensure hardware and firmware versions are fetched.

        Both version queries use synchronous request/response matching.
        Includes retry with buffer flush between attempts, matching the
        proven HACS approach.

        Returns True if both versions were obtained successfully.
        """
        if not self._rxmodule:
            return False

        # Query hardware version with retry
        hw_version = None
        for attempt in range(3):
            hw, _fw_unused = await self.hass.async_add_executor_job(
                self._query_hw_version
            )
            if hw and hw not in {"unknown", "error"}:
                hw_version = hw
                break
            if attempt < 2:
                wait_time = 0.5 * (attempt + 1)
                _LOGGER.debug(
                    "Hardware version query failed (attempt %d/3), retrying in %.1fs",
                    attempt + 1,
                    wait_time,
                )
                await asyncio.sleep(wait_time)
                # Flush serial buffer before retry to clear remaining stale data
                await self.hass.async_add_executor_job(
                    self._rxmodule.flush_serial_buffer
                )

        # Query firmware version with retry
        fw_version = None
        for attempt in range(3):
            fw = await self.hass.async_add_executor_job(self._query_fw_version)
            if fw and fw not in {"unknown", "error"}:
                fw_version = fw
                break
            if attempt < 2:
                wait_time = 0.5 * (attempt + 1)
                _LOGGER.debug(
                    "Firmware version query failed (attempt %d/3), retrying in %.1fs",
                    attempt + 1,
                    wait_time,
                )
                await asyncio.sleep(wait_time)
                await self.hass.async_add_executor_job(
                    self._rxmodule.flush_serial_buffer
                )

        self.hw_version = hw_version or "unknown"
        self.fw_version = fw_version or "unknown"

        if not hw_version and not fw_version:
            _LOGGER.warning("Version query failed")
            return False
        return True

    def _query_hw_version(self) -> tuple[str | None, None]:
        """Query hardware version (blocking). Returns (hw_version, None)."""
        if not self._rxmodule:
            return (None, None)
        try:
            result, hw_bytes = self._rxmodule.query_hw_version(timeout=5.0)
            if result == ErrorCode.SUCCESS:
                # Find null terminator and decode
                null_idx = hw_bytes.find(0)
                if null_idx >= 0:
                    hw_bytes = hw_bytes[:null_idx]
                hw_str = hw_bytes.decode("ascii", errors="ignore").strip()
                if hw_str:
                    return (hw_str, None)
            elif result == ErrorCode.ERR_FAILSTATE:
                _LOGGER.debug("HW query: device in failstate")
            else:
                _LOGGER.debug("HW query failed: 0x%02x", result)
        except _SERIAL_VALUE_ERRORS as e:
            _LOGGER.debug("HW query exception: %s", e)
        return (None, None)

    def _query_fw_version(self) -> str | None:
        """Query firmware version (blocking). Returns fw_version string or None."""
        if not self._rxmodule:
            return None
        try:
            result, major, minor, incomplete = self._rxmodule.query_fw_version(
                timeout=5.0
            )
            if result == ErrorCode.SUCCESS:
                version = f"{major}.{minor}"
                if incomplete:
                    version += " (incomplete)"
                return version
            if result == ErrorCode.ERR_FAILSTATE:
                _LOGGER.debug("FW query: device in failstate")
            else:
                _LOGGER.debug("FW query failed: 0x%02x", result)
        except _SERIAL_VALUE_ERRORS as e:
            _LOGGER.debug("FW query exception: %s", e)
        return None

    # ═══════════════════════════════════════════════════════════════════════════════
    # USB DEVICE DISCOVERY
    # ═══════════════════════════════════════════════════════════════════════════════

    def _find_usb_device(self) -> tuple[str, str, int, int] | None:
        """Find EASYWAVE device by VID/PID.

        This is a blocking call and should only be executed in an executor.
        Searches through all supported device types.

        Returns: (device_path, serial_number, vid, pid) or None if not found
        """
        ports = list(serial.tools.list_ports.comports())

        for port in ports:
            if (port.vid, port.pid) in SUPPORTED_USB_IDS:
                # Test open/close
                if self._test_serial_port(port.device):
                    return (
                        port.device,
                        port.serial_number or "unknown",
                        port.vid or 0,
                        port.pid or 0,
                    )

        return None

    def _test_serial_port(self, port_path: str) -> bool:
        """Test if a serial port can be opened (blocking)."""
        try:
            test_port = serial.Serial(
                port=port_path,
                baudrate=self.BAUDRATE,
                timeout=0.5,
            )
            test_port.close()
        except _SERIAL_ERRORS:
            return False
        else:
            return True

    # ═══════════════════════════════════════════════════════════════════════════════
    # RECONNECT
    # ═══════════════════════════════════════════════════════════════════════════════

    async def reconnect(self) -> bool:
        """Reconnect to RX11 with delay and exponential backoff.

        Implements pattern from RxModule:
        - Adds delay if recently disconnected for device reset
        - Increments reconnect attempt counter
        - Searches device freshly (device_path was cleared on disconnect)
        - Calls reconnect callback on success

        Returns:
            True if connection successful, False otherwise
        """
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
