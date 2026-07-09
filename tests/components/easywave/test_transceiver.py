"""Tests for the Easywave RX11Transceiver gateway wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.easywave.transceiver import RX11Transceiver
from homeassistant.core import HomeAssistant

DEVICE_PATH = "/dev/ttyACM0"
GATEWAY_PATH = "homeassistant.components.easywave.transceiver.EasywaveGateway"


@pytest.fixture
def mock_gateway() -> MagicMock:
    """Return a mock EasywaveGateway."""
    gateway = MagicMock()
    gateway.is_connected = False
    gateway.device_path = None
    gateway.usb_serial_number = None
    gateway.hw_version = None
    gateway.fw_version = None
    gateway.connect = AsyncMock(return_value=True)
    gateway.disconnect = AsyncMock()
    gateway.stop = AsyncMock()
    gateway.reconnect = AsyncMock(return_value=True)
    gateway.cancel_pending_receives = AsyncMock()
    gateway.ew = MagicMock()
    gateway.ew.receive_ex = AsyncMock(return_value=None)
    return gateway


@pytest.fixture
def transceiver(hass: HomeAssistant, mock_gateway: MagicMock) -> RX11Transceiver:
    """Return an RX11Transceiver with a mocked gateway."""
    with patch(GATEWAY_PATH, return_value=mock_gateway):
        return RX11Transceiver(hass, DEVICE_PATH)


async def test_connect_delegates_to_gateway(
    transceiver: RX11Transceiver, mock_gateway: MagicMock
) -> None:
    """Connect delegates to the library gateway."""
    mock_gateway.is_connected = True
    mock_gateway.device_path = DEVICE_PATH

    assert await transceiver.connect() is True
    mock_gateway.connect.assert_awaited_once()


async def test_disconnect_and_dispose_delegate_to_gateway(
    transceiver: RX11Transceiver, mock_gateway: MagicMock
) -> None:
    """Disconnect and dispose delegate to the library gateway."""
    await transceiver.disconnect()
    await transceiver.dispose()

    mock_gateway.disconnect.assert_awaited_once()
    mock_gateway.stop.assert_awaited_once()


async def test_reconnect_delegates_to_gateway(
    transceiver: RX11Transceiver, mock_gateway: MagicMock
) -> None:
    """Reconnect delegates to the library gateway."""
    assert await transceiver.reconnect() is True
    mock_gateway.reconnect.assert_awaited_once()


async def test_receive_telegram_delegates_to_gateway(
    transceiver: RX11Transceiver, mock_gateway: MagicMock
) -> None:
    """Receive and cancel operations delegate to the library facade."""
    assert await transceiver.receive_telegram(timeout=5.0) is None
    await transceiver.cancel_pending_receives()

    mock_gateway.ew.receive_ex.assert_awaited_once_with(timeout=5.0)
    mock_gateway.cancel_pending_receives.assert_awaited_once()


async def test_connected_callback_is_forwarded(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Gateway connect events invoke the registered callback."""
    callback = MagicMock()
    with patch(GATEWAY_PATH, return_value=mock_gateway):
        transceiver = RX11Transceiver(hass, DEVICE_PATH)
        transceiver.set_connected_callback(callback)
        transceiver._notify_connected(MagicMock())

    await hass.async_block_till_done()
    callback.assert_called_once()


async def test_disconnect_callback_is_forwarded(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Gateway disconnect events invoke the registered callback."""
    callback = MagicMock()
    with patch(GATEWAY_PATH, return_value=mock_gateway):
        transceiver = RX11Transceiver(hass, DEVICE_PATH)
        transceiver.set_disconnect_callback(callback)
        transceiver._notify_disconnect()

    await hass.async_block_till_done()
    callback.assert_called_once()


async def test_connected_notify_without_callback(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Connect notifications are ignored when no callback is registered."""
    with patch(GATEWAY_PATH, return_value=mock_gateway):
        transceiver = RX11Transceiver(hass, DEVICE_PATH)
        transceiver._notify_connected(MagicMock())


async def test_disconnect_notify_without_callback(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Disconnect notifications are ignored when no callback is registered."""
    with patch(GATEWAY_PATH, return_value=mock_gateway):
        transceiver = RX11Transceiver(hass, DEVICE_PATH)
        transceiver._notify_disconnect()


async def test_connected_notify_logs_callback_error(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Connect callback scheduling errors are logged without raising."""
    callback = MagicMock()
    with patch(GATEWAY_PATH, return_value=mock_gateway):
        transceiver = RX11Transceiver(hass, DEVICE_PATH)
        transceiver.set_connected_callback(callback)
        with patch.object(
            hass.loop, "call_soon_threadsafe", side_effect=RuntimeError("loop closed")
        ):
            transceiver._notify_connected(MagicMock())

    callback.assert_not_called()


async def test_disconnect_notify_logs_callback_error(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Disconnect callback scheduling errors are logged without raising."""
    callback = MagicMock()
    with patch(GATEWAY_PATH, return_value=mock_gateway):
        transceiver = RX11Transceiver(hass, DEVICE_PATH)
        transceiver.set_disconnect_callback(callback)
        with patch.object(
            hass.loop, "call_soon_threadsafe", side_effect=OSError("loop closed")
        ):
            transceiver._notify_disconnect()

    callback.assert_not_called()


def test_properties_proxy_gateway_state(mock_gateway: MagicMock) -> None:
    """Transceiver properties mirror the gateway state."""
    mock_gateway.is_connected = True
    mock_gateway.device_path = DEVICE_PATH
    mock_gateway.usb_serial_number = "12345"
    mock_gateway.hw_version = "RX11 v1.0"
    mock_gateway.fw_version = "2.5"

    with patch(GATEWAY_PATH, return_value=mock_gateway):
        transceiver = RX11Transceiver(MagicMock(), DEVICE_PATH)

    assert transceiver.is_connected is True
    assert transceiver.device_path == DEVICE_PATH
    assert transceiver.usb_serial_number == "12345"
    assert transceiver.hw_version == "RX11 v1.0"
    assert transceiver.fw_version == "2.5"
