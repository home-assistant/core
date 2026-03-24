"""Tests for the Easywave RX11Transceiver."""

from __future__ import annotations

import asyncio
import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

from easywave_home_control import RX11ErrorCode
import pytest
import serial

from homeassistant.components.easywave.transceiver import RX11Transceiver
from homeassistant.core import HomeAssistant

DEVICE_PATH = "/dev/ttyACM0"

# Simulated library return values
_HW_BYTES = b"RX11 v1.0\x00\x00"
_HW_OK = (RX11ErrorCode.SUCCESS, _HW_BYTES)
_HW_FAIL = (RX11ErrorCode.ERR_RF_TIMEOUT, b"")
_FW_OK = (RX11ErrorCode.SUCCESS, 2, 5, False)  # major=2, minor=5
_FW_INCOMPLETE = (RX11ErrorCode.SUCCESS, 1, 0, True)  # incomplete firmware
_FW_FAIL = (RX11ErrorCode.ERR_RF_TIMEOUT, 0, 0, False)

# Keep a reference to the real asyncio.sleep before any patching.
_real_sleep = asyncio.sleep


@pytest.fixture
def mock_device() -> MagicMock:
    """Return a mock RX11Device with all required methods pre-configured."""
    device = MagicMock()
    device.connect = AsyncMock(return_value=True)
    device.disconnect = AsyncMock()
    device.ping_request = AsyncMock(return_value=True)
    device.query_hw_version = AsyncMock(return_value=_HW_OK)
    device.query_fw_version = AsyncMock(return_value=_FW_OK)
    device.set_disconnect_callback = MagicMock()
    device.set_reconnect_callback = MagicMock()
    return device


@pytest.fixture
def transceiver(hass: HomeAssistant) -> RX11Transceiver:
    """Return an RX11Transceiver with an explicit device path."""
    return RX11Transceiver(hass, DEVICE_PATH)


def _patch_device(mock_device: MagicMock):
    """Context manager: patch RX11Device constructor to return mock_device."""
    return patch(
        "homeassistant.components.easywave.transceiver.RX11Device",
        return_value=mock_device,
    )


def _patch_sleep():
    """Context manager: replace asyncio.sleep with a fast version.

    Uses the real asyncio.sleep(0) so the event loop still yields once per
    call — this ensures task cancellation works correctly in tests that start
    a background health-check task via connect().
    """

    async def _fast_sleep(_delay: float) -> None:
        await _real_sleep(0)

    return patch("asyncio.sleep", new=_fast_sleep)


# ── connect / explicit device path ───────────────────────────────────────────


async def test_connect_success(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test successful connect sets state, fetches versions, and registers callbacks."""
    with _patch_device(mock_device), _patch_sleep():
        result = await transceiver.connect()

        assert result is True
        assert transceiver.is_connected is True
        assert transceiver.device_path == DEVICE_PATH
        assert transceiver.hw_version == "RX11 v1.0"
        assert transceiver.fw_version == "2.5"
        mock_device.connect.assert_awaited_once()
        mock_device.set_disconnect_callback.assert_called_once_with(
            transceiver._on_device_disconnect
        )
        mock_device.set_reconnect_callback.assert_called_once_with(
            transceiver._on_device_reconnect
        )
        await transceiver.disconnect()


async def test_connect_already_connected(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test connect is a no-op when already connected."""
    with _patch_device(mock_device), _patch_sleep():
        await transceiver.connect()
        result = await transceiver.connect()
        await transceiver.disconnect()

    assert result is True
    mock_device.connect.assert_awaited_once()


async def test_connect_when_disposed(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test connect returns False immediately after dispose."""
    transceiver._disposed = True

    with _patch_device(mock_device):
        result = await transceiver.connect()

    assert result is False
    mock_device.connect.assert_not_called()


async def test_connect_device_refuses_connection(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test connect returns False when RX11Device.connect() returns False."""
    mock_device.connect = AsyncMock(return_value=False)

    with _patch_device(mock_device):
        result = await transceiver.connect()

    assert result is False
    assert transceiver.is_connected is False
    mock_device.disconnect.assert_awaited_once()


async def test_connect_version_fetch_fails(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test connect disconnects and returns False when version fetch fails."""
    mock_device.query_hw_version = AsyncMock(return_value=_HW_FAIL)
    mock_device.query_fw_version = AsyncMock(return_value=_FW_FAIL)

    with _patch_device(mock_device), _patch_sleep():
        result = await transceiver.connect()

    assert result is False
    assert transceiver.is_connected is False
    mock_device.disconnect.assert_awaited()


# ── connect / device discovery ────────────────────────────────────────────────


async def test_connect_finds_device_by_vid_pid(
    hass: HomeAssistant,
    mock_device: MagicMock,
) -> None:
    """Test connect scans by VID/PID when no device path is configured."""
    transceiver = RX11Transceiver(hass)
    mock_port = MagicMock()
    mock_port.vid = 0x155A
    mock_port.pid = 0x1014
    mock_port.device = DEVICE_PATH
    mock_port.serial_number = "SN-42"

    with (
        _patch_device(mock_device),
        _patch_sleep(),
        patch(
            "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
            return_value=[mock_port],
        ),
        patch("homeassistant.components.easywave.transceiver.serial.Serial"),
    ):
        result = await transceiver.connect()
        await transceiver.disconnect()

    assert result is True
    assert transceiver.device_path == DEVICE_PATH
    assert transceiver.usb_serial_number == "SN-42"


async def test_connect_no_device_found(
    hass: HomeAssistant,
) -> None:
    """Test connect returns False when VID/PID scan finds nothing."""
    transceiver = RX11Transceiver(hass)

    with patch(
        "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
        return_value=[],
    ):
        result = await transceiver.connect()

    assert result is False
    assert transceiver.is_connected is False


# ── disconnect ────────────────────────────────────────────────────────────────


async def test_disconnect_clears_state(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test disconnect clears callbacks, device reference, and connected flag."""
    with _patch_device(mock_device), _patch_sleep():
        await transceiver.connect()
        await transceiver.disconnect()

    assert transceiver.is_connected is False
    assert transceiver._device is None
    mock_device.set_disconnect_callback.assert_called_with(None)
    mock_device.set_reconnect_callback.assert_called_with(None)
    mock_device.disconnect.assert_awaited()


async def test_disconnect_stops_health_check(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test disconnect cancels the running health check task."""
    with _patch_device(mock_device), _patch_sleep():
        await transceiver.connect()
        assert transceiver._health_check_task is not None
        await transceiver.disconnect()

    assert transceiver._health_check_task is None


async def test_disconnect_idempotent(
    transceiver: RX11Transceiver,
) -> None:
    """Test disconnect can safely be called multiple times without error."""
    await transceiver.disconnect()
    await transceiver.disconnect()

    assert transceiver.is_connected is False


# ── dispose ───────────────────────────────────────────────────────────────────


async def test_dispose_sets_disposed_flag_and_disconnects(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test dispose marks the transceiver as disposed and disconnects device."""
    with _patch_device(mock_device), _patch_sleep():
        await transceiver.connect()

    await transceiver.dispose()

    assert transceiver._disposed is True
    assert transceiver.is_connected is False
    mock_device.disconnect.assert_awaited()


async def test_dispose_blocks_future_connect(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test connect returns False after dispose."""
    await transceiver.dispose()

    with _patch_device(mock_device):
        result = await transceiver.connect()

    assert result is False
    mock_device.connect.assert_not_called()


async def test_dispose_blocks_future_reconnect(
    transceiver: RX11Transceiver,
) -> None:
    """Test reconnect returns False after dispose."""
    await transceiver.dispose()

    result = await transceiver.reconnect()

    assert result is False


async def test_dispose_idempotent(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test second dispose call is a no-op — device disconnect is not called again."""
    with _patch_device(mock_device), _patch_sleep():
        await transceiver.connect()

    await transceiver.dispose()
    disconnect_count = mock_device.disconnect.await_count

    await transceiver.dispose()

    assert mock_device.disconnect.await_count == disconnect_count


# ── reconnect ─────────────────────────────────────────────────────────────────


async def test_reconnect_success(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test reconnect disconnects and re-connects successfully."""
    with _patch_device(mock_device), _patch_sleep():
        result = await transceiver.reconnect()
        await transceiver.disconnect()

    assert result is True
    assert transceiver._reconnect_attempts == 0


async def test_reconnect_when_disposed(
    transceiver: RX11Transceiver,
) -> None:
    """Test reconnect returns False immediately when disposed."""
    transceiver._disposed = True

    result = await transceiver.reconnect()

    assert result is False


async def test_reconnect_when_connect_fails(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test reconnect returns False and increments attempt counter on failure."""
    mock_device.connect = AsyncMock(return_value=False)

    with _patch_device(mock_device), _patch_sleep():
        result = await transceiver.reconnect()

    assert result is False
    assert transceiver._reconnect_attempts == 1


# ── health check ──────────────────────────────────────────────────────────────


async def test_health_check_started_after_connect(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test a health check task is started after a successful connect."""
    with _patch_device(mock_device), _patch_sleep():
        await transceiver.connect()
        assert transceiver._health_check_task is not None
        await transceiver.disconnect()


async def test_health_check_ping_success(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test health check loop exits cleanly when stopping is requested after one ping."""
    transceiver._device = mock_device
    transceiver.is_connected = True

    call_count = 0

    async def one_shot_sleep(_: float) -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= 1:
            transceiver._health_check_stopping = True

    with patch("asyncio.sleep", side_effect=one_shot_sleep):
        await transceiver._health_check_loop()

    mock_device.ping_request.assert_awaited_once()
    assert transceiver.is_connected is True


async def test_health_check_three_failures_trigger_disconnect(
    hass: HomeAssistant,
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test health check triggers disconnect after 3 consecutive ping failures."""
    mock_device.ping_request = AsyncMock(return_value=False)
    disconnect_callback = MagicMock()
    transceiver.set_disconnect_callback(disconnect_callback)
    transceiver._device = mock_device
    transceiver.is_connected = True

    with _patch_sleep():
        await transceiver._health_check_loop()

    await hass.async_block_till_done()

    disconnect_callback.assert_called_once()
    assert mock_device.ping_request.await_count == 3


async def test_health_check_resets_counter_on_recovery(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test health check failure counter resets after a successful ping (no disconnect)."""
    call_count = 0

    async def alternating_ping() -> bool:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return False  # Two consecutive failures
        transceiver._health_check_stopping = True
        return True  # Recovery — counter resets

    mock_device.ping_request = AsyncMock(side_effect=alternating_ping)
    transceiver._device = mock_device
    transceiver.is_connected = True

    with _patch_sleep():
        await transceiver._health_check_loop()

    # Two consecutive failures (< 3) must not trigger disconnect
    assert transceiver.is_connected is True


# ── device callbacks ──────────────────────────────────────────────────────────


async def test_on_device_disconnect_notifies_callback(
    hass: HomeAssistant,
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test library disconnect callback notifies registered listeners."""
    callback = MagicMock()
    transceiver.set_disconnect_callback(callback)
    transceiver._device = mock_device
    transceiver.is_connected = True

    transceiver._on_device_disconnect()
    await hass.async_block_till_done()

    callback.assert_called_once()


async def test_on_device_reconnect_logs_info(
    transceiver: RX11Transceiver,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test library reconnect callback logs an info-level message."""
    with caplog.at_level(
        logging.INFO,
        logger="homeassistant.components.easywave.transceiver",
    ):
        transceiver._on_device_reconnect()

    assert "reconnect" in caplog.text.lower()


# ── version fetch ─────────────────────────────────────────────────────────────


async def test_ensure_versions_fetched_success(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test _ensure_versions_fetched parses hardware and firmware version strings."""
    transceiver._device = mock_device

    result = await transceiver._ensure_versions_fetched()

    assert result is True
    assert transceiver.hw_version == "RX11 v1.0"
    assert transceiver.fw_version == "2.5"


async def test_ensure_versions_fetched_no_device(
    transceiver: RX11Transceiver,
) -> None:
    """Test _ensure_versions_fetched returns False when no device is available."""
    result = await transceiver._ensure_versions_fetched()

    assert result is False


async def test_ensure_versions_fetched_incomplete_firmware(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test _ensure_versions_fetched appends '(incomplete)' for incomplete firmware."""
    mock_device.query_fw_version = AsyncMock(return_value=_FW_INCOMPLETE)
    transceiver._device = mock_device

    result = await transceiver._ensure_versions_fetched()

    assert result is True
    assert transceiver.fw_version is not None
    assert "incomplete" in transceiver.fw_version


async def test_ensure_versions_fetched_all_queries_fail(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test _ensure_versions_fetched returns False when all queries fail."""
    mock_device.query_hw_version = AsyncMock(return_value=_HW_FAIL)
    mock_device.query_fw_version = AsyncMock(return_value=_FW_FAIL)
    transceiver._device = mock_device

    with _patch_sleep():
        result = await transceiver._ensure_versions_fetched()

    assert result is False


# ── notify_disconnect error handling ─────────────────────────────────────────


async def test_notify_disconnect_callback_raises_oserror(
    transceiver: RX11Transceiver,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _notify_disconnect logs an error when the callback raises OSError."""
    transceiver.set_disconnect_callback(MagicMock(side_effect=OSError("fail")))

    with caplog.at_level(
        logging.ERROR,
        logger="homeassistant.components.easywave.transceiver",
    ):
        transceiver._notify_disconnect()

    assert "Error in disconnect callback" in caplog.text


async def test_notify_disconnect_callback_raises_runtime_error(
    transceiver: RX11Transceiver,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _notify_disconnect logs an error when the callback raises RuntimeError."""
    transceiver.set_disconnect_callback(MagicMock(side_effect=RuntimeError("boom")))

    with caplog.at_level(
        logging.ERROR,
        logger="homeassistant.components.easywave.transceiver",
    ):
        transceiver._notify_disconnect()

    assert "Error in disconnect callback" in caplog.text


# ── connect / VID-PID path failure branches ───────────────────────────────────


async def test_connect_vid_pid_try_connect_fails(
    hass: HomeAssistant,
    mock_device: MagicMock,
) -> None:
    """Test connect returns False when _try_connect_to_path fails after VID/PID discovery."""
    transceiver = RX11Transceiver(hass)
    mock_port = MagicMock()
    mock_port.vid = 0x155A
    mock_port.pid = 0x1014
    mock_port.device = DEVICE_PATH
    mock_port.serial_number = "SN-99"

    mock_device.connect = AsyncMock(return_value=False)

    with (
        _patch_device(mock_device),
        _patch_sleep(),
        patch(
            "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
            return_value=[mock_port],
        ),
        patch(
            "homeassistant.components.easywave.transceiver.serial.Serial",
        ),
    ):
        result = await transceiver.connect()

    assert result is False
    assert transceiver.is_connected is False


async def test_connect_serial_error_during_vid_pid_search(
    hass: HomeAssistant,
) -> None:
    """Test connect returns False when comports() raises inside _find_usb_device."""

    transceiver = RX11Transceiver(hass)  # no device_path → goes to VID/PID search

    with patch(
        "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
        side_effect=serial.SerialException("port scan failed"),
    ):
        result = await transceiver.connect()

    assert result is False


# ── _try_connect_to_path / serial error ──────────────────────────────────────


async def test_try_connect_device_constructor_returns_none(
    transceiver: RX11Transceiver,
) -> None:
    """Test _try_connect_to_path returns False when device constructor returns None."""
    with patch(
        "homeassistant.components.easywave.transceiver.RX11Device",
        return_value=None,
    ):
        result = await transceiver._try_connect_to_path(DEVICE_PATH)

    assert result is False


async def test_try_connect_serial_error_on_connect(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test _try_connect_to_path returns False when library connect() raises SerialException."""

    mock_device.connect = AsyncMock(side_effect=serial.SerialException("port error"))

    with _patch_device(mock_device):
        result = await transceiver._try_connect_to_path(DEVICE_PATH)

    assert result is False
    mock_device.disconnect.assert_awaited_once()


# ── _refresh_usb_identity ─────────────────────────────────────────────────────


async def test_refresh_usb_identity_no_device_path(
    hass: HomeAssistant,
) -> None:
    """Test _refresh_usb_identity returns immediately when no device_path is set."""
    transceiver = RX11Transceiver(hass)
    assert transceiver.device_path is None

    # Should not raise
    await transceiver._refresh_usb_identity()

    assert transceiver.usb_serial_number is None


async def test_refresh_usb_identity_port_found(
    transceiver: RX11Transceiver,
) -> None:
    """Test _refresh_usb_identity updates usb_serial_number from the port."""
    transceiver.usb_serial_number = None
    mock_port = MagicMock()
    mock_port.device = DEVICE_PATH
    mock_port.serial_number = "SN-NEW"

    with patch(
        "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
        return_value=[mock_port],
    ):
        await transceiver._refresh_usb_identity()

    assert transceiver.usb_serial_number == "SN-NEW"


async def test_refresh_usb_identity_device_swap_detected(
    transceiver: RX11Transceiver,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _refresh_usb_identity detects a device swap and clears version cache."""
    transceiver.usb_serial_number = "OLD-SN"
    transceiver.hw_version = "1.0"
    transceiver.fw_version = "2.0"
    mock_port = MagicMock()
    mock_port.device = DEVICE_PATH
    mock_port.serial_number = "NEW-SN"

    with (
        caplog.at_level(
            logging.INFO,
            logger="homeassistant.components.easywave.transceiver",
        ),
        patch(
            "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
            return_value=[mock_port],
        ),
    ):
        await transceiver._refresh_usb_identity()

    assert transceiver.usb_serial_number == "NEW-SN"
    assert transceiver.hw_version is None
    assert transceiver.fw_version is None
    assert "swap" in caplog.text.lower()


async def test_refresh_usb_identity_serial_error(
    transceiver: RX11Transceiver,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _refresh_usb_identity handles SerialException gracefully."""

    with (
        caplog.at_level(
            logging.DEBUG,
            logger="homeassistant.components.easywave.transceiver",
        ),
        patch(
            "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
            side_effect=serial.SerialException("read error"),
        ),
    ):
        await transceiver._refresh_usb_identity()

    assert "Could not refresh USB identity" in caplog.text


# ── _start_health_check / already running ────────────────────────────────────


async def test_start_health_check_already_running(
    transceiver: RX11Transceiver,
) -> None:
    """Test _start_health_check is a no-op when a task is already running."""
    sentinel = MagicMock()
    transceiver._health_check_task = sentinel

    await transceiver._start_health_check()

    assert transceiver._health_check_task is sentinel


# ── health check / edge cases ─────────────────────────────────────────────────


async def test_health_check_skips_when_not_connected(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test health check loop skips ping when transceiver is marked disconnected."""
    transceiver._device = mock_device
    transceiver.is_connected = False  # already offline

    call_count = 0

    async def one_shot_sleep(_: float) -> None:
        nonlocal call_count
        call_count += 1
        transceiver._health_check_stopping = True

    with patch("asyncio.sleep", side_effect=one_shot_sleep):
        await transceiver._health_check_loop()

    mock_device.ping_request.assert_not_called()


async def test_health_check_ping_raises_serial_exception(
    hass: HomeAssistant,
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test health check treats ping SerialException as a failure (not a crash)."""

    ping_count = 0

    async def raise_then_stop() -> bool:
        nonlocal ping_count
        ping_count += 1
        if ping_count < 3:
            raise serial.SerialException("port gone")
        # On 3rd call stop the loop; still counts as failure
        transceiver._health_check_stopping = True
        raise serial.SerialException("port gone")

    mock_device.ping_request = AsyncMock(side_effect=raise_then_stop)
    transceiver._device = mock_device
    transceiver.is_connected = True

    with _patch_sleep():
        await transceiver._health_check_loop()

    await hass.async_block_till_done()


async def test_health_check_outer_serial_exception(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test health check recovers from an unexpected serial error via outer handler."""

    call_count = 0

    async def sleep_with_exception(_: float) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise serial.SerialException("unexpected error")
        transceiver._health_check_stopping = True

    transceiver._device = mock_device
    transceiver.is_connected = True

    with (
        caplog.at_level(
            logging.DEBUG,
            logger="homeassistant.components.easywave.transceiver",
        ),
        patch("asyncio.sleep", side_effect=sleep_with_exception),
    ):
        await transceiver._health_check_loop()

    assert "Error in health check" in caplog.text


# ── _handle_device_disconnect / already offline ───────────────────────────────


async def test_handle_device_disconnect_already_offline(
    transceiver: RX11Transceiver,
) -> None:
    """Test _handle_device_disconnect is a no-op when already marked offline."""
    transceiver.is_connected = False
    callback = MagicMock()
    transceiver.set_disconnect_callback(callback)

    await transceiver._handle_device_disconnect()

    callback.assert_not_called()


# ── version fetch / exception paths ──────────────────────────────────────────


async def test_ensure_versions_fetched_hw_exception_then_success(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test _ensure_versions_fetched retries hw query after SerialException."""

    call_count = 0

    async def hw_fail_once(**kwargs: object) -> tuple:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise serial.SerialException("timeout")
        return _HW_OK

    mock_device.query_hw_version = AsyncMock(side_effect=hw_fail_once)
    transceiver._device = mock_device

    with _patch_sleep():
        result = await transceiver._ensure_versions_fetched()

    assert result is True
    assert transceiver.hw_version == "RX11 v1.0"


async def test_ensure_versions_fetched_fw_exception_then_success(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test _ensure_versions_fetched retries fw query after SerialException."""

    call_count = 0

    async def fw_fail_once(**kwargs: object) -> tuple:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise serial.SerialException("timeout")
        return _FW_OK

    mock_device.query_fw_version = AsyncMock(side_effect=fw_fail_once)
    transceiver._device = mock_device

    with _patch_sleep():
        result = await transceiver._ensure_versions_fetched()

    assert result is True
    assert transceiver.fw_version == "2.5"


# ── _test_serial_port / serial error ─────────────────────────────────────────


def test_test_serial_port_serial_exception(
    transceiver: RX11Transceiver,
) -> None:
    """Test _test_serial_port returns False when SerialException is raised."""

    with patch(
        "homeassistant.components.easywave.transceiver.serial.Serial",
        side_effect=serial.SerialException("port busy"),
    ):
        result = transceiver._test_serial_port(DEVICE_PATH)

    assert result is False


# ── reconnect / delay and error paths ────────────────────────────────────────


async def test_reconnect_applies_delay_after_recent_disconnect(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test reconnect waits for device reset when recently disconnected."""

    # Simulate a very recent disconnect (0.1 seconds ago)
    transceiver._last_disconnect_time = time.time() - 0.1

    sleeps: list[float] = []

    async def _fast_sleep_capture(delay: float) -> None:
        sleeps.append(delay)
        await _real_sleep(0)

    with _patch_device(mock_device), patch("asyncio.sleep", new=_fast_sleep_capture):
        result = await transceiver.reconnect()
        await transceiver.disconnect()

    assert result is True
    # First sleep should be the reconnect delay (close to 0.9s)
    assert sleeps[0] > 0.5


async def test_reconnect_serial_error_returns_false(
    transceiver: RX11Transceiver,
    mock_device: MagicMock,
) -> None:
    """Test reconnect returns False when a serial error occurs during disconnect."""

    with patch.object(
        transceiver,
        "disconnect",
        side_effect=serial.SerialException("port gone"),
    ):
        result = await transceiver.reconnect()

    assert result is False
