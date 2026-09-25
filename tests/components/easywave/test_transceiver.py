"""Tests for the Easywave RX11Transceiver gateway wrapper."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.easywave.const import SUPPORTED_USB_IDS
from homeassistant.components.easywave.transceiver import (
    RX11Transceiver,
    resolve_gateway_port,
)
from homeassistant.core import HomeAssistant

DEVICE_PATH = "/dev/ttyACM0"
GATEWAY_PATH = "homeassistant.components.easywave.transceiver.EasywaveGateway"
RESOLVE_PATH = "homeassistant.components.easywave.transceiver.resolve_gateway_port"


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
        return RX11Transceiver(hass, device_path=DEVICE_PATH)


def _gateway_callbacks(mock_gateway_cls: MagicMock) -> Any:
    """Return the gateway callbacks registered with the library."""
    return mock_gateway_cls.call_args.kwargs["callbacks"]


async def test_connect_prepares_connection_before_gateway_connect(
    transceiver: RX11Transceiver, mock_gateway: MagicMock
) -> None:
    """Connect resolves the configured gateway before opening it."""
    with patch.object(
        transceiver, "_prepare_connection", AsyncMock(return_value=True)
    ) as mock_prepare:
        assert await transceiver.connect() is True

    mock_prepare.assert_awaited_once()
    mock_gateway.connect.assert_awaited_once()


async def test_connect_fails_when_configured_port_unresolved(
    transceiver: RX11Transceiver, mock_gateway: MagicMock
) -> None:
    """Connect aborts when the configured gateway cannot be resolved."""
    with patch.object(
        transceiver, "_prepare_connection", AsyncMock(return_value=False)
    ):
        assert await transceiver.connect() is False

    mock_gateway.connect.assert_not_called()


async def test_prepare_connection_sets_gateway_target(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Connection preparation recreates the gateway with the resolved port."""
    with patch(GATEWAY_PATH, return_value=mock_gateway) as mock_gateway_cls:
        transceiver = RX11Transceiver(
            hass,
            {"usb_serial_number": "222", "device_path": "/dev/ttyACM0"},
        )
        with patch(RESOLVE_PATH, return_value=DEVICE_PATH):
            assert await transceiver._prepare_connection() is True

    assert mock_gateway_cls.call_args_list[-1].args[0].port == DEVICE_PATH
    mock_gateway.stop.assert_awaited()


async def test_prepare_connection_falls_back_to_sole_rx11_when_serial_missing(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Connection preparation accepts a replacement RX11 when it is the only one."""
    with patch(GATEWAY_PATH, return_value=mock_gateway) as mock_gateway_cls:
        transceiver = RX11Transceiver(
            hass,
            {"usb_serial_number": "missing", "device_path": "/dev/ttyACM0"},
        )
        with patch(RESOLVE_PATH, return_value="/dev/ttyACM1"):
            assert await transceiver._prepare_connection() is True

    assert mock_gateway_cls.call_args_list[-1].args[0].port == "/dev/ttyACM1"


async def test_prepare_connection_clears_path_when_unresolved(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Unresolved ports recreate the gateway without an active path."""
    with patch(GATEWAY_PATH, return_value=mock_gateway) as mock_gateway_cls:
        transceiver = RX11Transceiver(
            hass,
            {"usb_serial_number": "missing", "device_path": "/dev/ttyACM0"},
        )
        with patch(RESOLVE_PATH, return_value=None):
            assert await transceiver._prepare_connection() is False

    assert mock_gateway_cls.call_args_list[-1].args[0].port is None
    mock_gateway.stop.assert_awaited()


async def test_prepare_connection_ignores_stop_errors_on_old_gateway(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Old gateway stop failures do not block reconnect preparation."""
    mock_gateway.stop = AsyncMock(side_effect=OSError("already closed"))
    with patch(GATEWAY_PATH, return_value=mock_gateway) as mock_gateway_cls:
        transceiver = RX11Transceiver(hass, device_path=DEVICE_PATH)
        with patch(RESOLVE_PATH, return_value=DEVICE_PATH):
            assert await transceiver._prepare_connection() is True

    assert mock_gateway_cls.call_args_list[-1].args[0].port == DEVICE_PATH


async def test_disconnect_and_dispose_delegate_to_gateway(
    transceiver: RX11Transceiver, mock_gateway: MagicMock
) -> None:
    """Disconnect and dispose delegate to the library gateway."""
    await transceiver.disconnect()
    await transceiver.dispose()

    mock_gateway.disconnect.assert_awaited_once()
    mock_gateway.stop.assert_awaited_once()


async def test_reconnect_prepares_connection_before_gateway_connect(
    transceiver: RX11Transceiver, mock_gateway: MagicMock
) -> None:
    """Reconnect rebuilds the gateway then connects from STOPPED state."""
    with patch.object(transceiver, "_prepare_connection", AsyncMock(return_value=True)):
        assert await transceiver.reconnect() is True

    mock_gateway.connect.assert_awaited_once()
    mock_gateway.reconnect.assert_not_called()


async def test_reconnect_fails_when_configured_port_unresolved(
    transceiver: RX11Transceiver, mock_gateway: MagicMock
) -> None:
    """Reconnect aborts when the configured gateway cannot be resolved."""
    with patch.object(
        transceiver, "_prepare_connection", AsyncMock(return_value=False)
    ):
        assert await transceiver.reconnect() is False

    mock_gateway.connect.assert_not_called()
    mock_gateway.reconnect.assert_not_called()


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
    with patch(GATEWAY_PATH, return_value=mock_gateway) as mock_gateway_cls:
        transceiver = RX11Transceiver(hass, device_path=DEVICE_PATH)
        transceiver.set_connected_callback(callback)
        _gateway_callbacks(mock_gateway_cls).on_connected(MagicMock())

    await hass.async_block_till_done()
    callback.assert_called_once()


async def test_disconnect_callback_is_forwarded(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Gateway disconnect events invoke the registered callback."""
    callback = MagicMock()
    with patch(GATEWAY_PATH, return_value=mock_gateway) as mock_gateway_cls:
        transceiver = RX11Transceiver(hass, device_path=DEVICE_PATH)
        transceiver.set_disconnect_callback(callback)
        _gateway_callbacks(mock_gateway_cls).on_disconnected()

    await hass.async_block_till_done()
    callback.assert_called_once()


async def test_connected_notify_without_callback(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Connect notifications are ignored when no callback is registered."""
    with patch(GATEWAY_PATH, return_value=mock_gateway) as mock_gateway_cls:
        RX11Transceiver(hass, device_path=DEVICE_PATH)
        _gateway_callbacks(mock_gateway_cls).on_connected(MagicMock())


async def test_disconnect_notify_without_callback(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Disconnect notifications are ignored when no callback is registered."""
    with patch(GATEWAY_PATH, return_value=mock_gateway) as mock_gateway_cls:
        RX11Transceiver(hass, device_path=DEVICE_PATH)
        _gateway_callbacks(mock_gateway_cls).on_disconnected()


async def test_connected_notify_logs_callback_error(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Connect callback scheduling errors are logged without raising."""
    callback = MagicMock()
    with patch(GATEWAY_PATH, return_value=mock_gateway) as mock_gateway_cls:
        transceiver = RX11Transceiver(hass, device_path=DEVICE_PATH)
        transceiver.set_connected_callback(callback)
        with patch.object(
            hass.loop, "call_soon_threadsafe", side_effect=RuntimeError("loop closed")
        ):
            _gateway_callbacks(mock_gateway_cls).on_connected(MagicMock())

    callback.assert_not_called()


async def test_disconnect_notify_logs_callback_error(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Disconnect callback scheduling errors are logged without raising."""
    callback = MagicMock()
    with patch(GATEWAY_PATH, return_value=mock_gateway) as mock_gateway_cls:
        transceiver = RX11Transceiver(hass, device_path=DEVICE_PATH)
        transceiver.set_disconnect_callback(callback)
        with patch.object(
            hass.loop, "call_soon_threadsafe", side_effect=OSError("loop closed")
        ):
            _gateway_callbacks(mock_gateway_cls).on_disconnected()

    callback.assert_not_called()


def test_properties_proxy_gateway_state(mock_gateway: MagicMock) -> None:
    """Transceiver properties mirror the gateway state."""
    mock_gateway.is_connected = True
    mock_gateway.device_path = DEVICE_PATH
    mock_gateway.usb_serial_number = "12345"
    mock_gateway.hw_version = "RX11 v1.0"
    mock_gateway.fw_version = "2.5"

    with patch(GATEWAY_PATH, return_value=mock_gateway):
        transceiver = RX11Transceiver(MagicMock(), device_path=DEVICE_PATH)

    assert transceiver.is_connected is True
    assert transceiver.device_path == DEVICE_PATH
    assert transceiver.usb_serial_number == "12345"
    assert transceiver.hw_version == "RX11 v1.0"
    assert transceiver.fw_version == "2.5"


def test_gateway_config_disables_library_auto_reconnect(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """The transceiver wrapper leaves reconnect handling to the coordinator."""
    with patch(GATEWAY_PATH, return_value=mock_gateway) as mock_gateway_cls:
        RX11Transceiver(hass, device_path=DEVICE_PATH)

    gateway_config = mock_gateway_cls.call_args.args[0]
    assert gateway_config.auto_reconnect is False


def test_resolve_gateway_port_prefers_usb_serial() -> None:
    """Port resolution matches the configured USB serial number."""
    port_a = MagicMock(
        device="/dev/ttyACM0", vid=0x155A, pid=0x1014, serial_number="111"
    )
    port_b = MagicMock(
        device="/dev/ttyACM1", vid=0x155A, pid=0x1014, serial_number="222"
    )

    with patch(
        "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
        return_value=[port_a, port_b],
    ):
        assert (
            resolve_gateway_port(
                SUPPORTED_USB_IDS,
                usb_serial="222",
            )
            == "/dev/ttyACM1"
        )


def test_resolve_gateway_port_falls_back_to_sole_rx11_when_serial_missing() -> None:
    """Port resolution accepts a replacement RX11 when it is the only one."""
    port = MagicMock(device="/dev/ttyACM0", vid=0x155A, pid=0x1014, serial_number="222")

    with patch(
        "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
        return_value=[port],
    ):
        assert (
            resolve_gateway_port(
                SUPPORTED_USB_IDS,
                usb_serial="missing",
            )
            == "/dev/ttyACM0"
        )


def test_resolve_gateway_port_rejects_replacement_when_disabled() -> None:
    """Strict resolution does not adopt a different sole RX11 stick."""
    port = MagicMock(device="/dev/ttyACM0", vid=0x155A, pid=0x1014, serial_number="222")

    with patch(
        "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
        return_value=[port],
    ):
        assert (
            resolve_gateway_port(
                SUPPORTED_USB_IDS,
                usb_serial="missing",
                device_path="/dev/ttyACM1",
                allow_replacement=False,
            )
            is None
        )


def test_resolve_gateway_port_returns_none_for_ambiguous_replacement() -> None:
    """Port resolution stays unresolved when multiple RX11s are present."""
    port_a = MagicMock(
        device="/dev/ttyACM0", vid=0x155A, pid=0x1014, serial_number="111"
    )
    port_b = MagicMock(
        device="/dev/ttyACM1", vid=0x155A, pid=0x1014, serial_number="222"
    )

    with patch(
        "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
        return_value=[port_a, port_b],
    ):
        assert (
            resolve_gateway_port(
                SUPPORTED_USB_IDS,
                usb_serial="missing",
            )
            is None
        )


def test_resolve_gateway_port_matches_configured_device_path() -> None:
    """Port resolution prefers an exact configured device path match."""
    port_a = MagicMock(
        device="/dev/ttyACM0", vid=0x155A, pid=0x1014, serial_number="111"
    )
    port_b = MagicMock(
        device="/dev/ttyACM1", vid=0x155A, pid=0x1014, serial_number="222"
    )

    with patch(
        "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
        return_value=[port_a, port_b],
    ):
        assert (
            resolve_gateway_port(
                SUPPORTED_USB_IDS,
                device_path="/dev/ttyACM1",
            )
            == "/dev/ttyACM1"
        )


def test_resolve_gateway_port_rejects_path_owned_by_other_serial() -> None:
    """Do not claim a reused path that belongs to a different serialized RX11."""
    other_stick = MagicMock(
        device="/dev/ttyACM0", vid=0x155A, pid=0x1014, serial_number="other"
    )
    replacement = MagicMock(
        device="/dev/ttyACM1", vid=0x155A, pid=0x1014, serial_number="replacement"
    )

    with patch(
        "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
        return_value=[other_stick, replacement],
    ):
        assert (
            resolve_gateway_port(
                SUPPORTED_USB_IDS,
                usb_serial="configured",
                device_path="/dev/ttyACM0",
            )
            is None
        )


def test_resolve_gateway_port_path_fallback_when_serial_absent_on_port() -> None:
    """A path match is allowed when the stick has no USB serial number."""
    port = MagicMock(device="/dev/ttyACM0", vid=0x155A, pid=0x1014, serial_number=None)

    with patch(
        "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
        return_value=[port],
    ):
        assert (
            resolve_gateway_port(
                SUPPORTED_USB_IDS,
                usb_serial="configured",
                device_path="/dev/ttyACM0",
                allow_replacement=False,
            )
            == "/dev/ttyACM0"
        )


def test_resolve_gateway_port_returns_none_when_comports_raises() -> None:
    """Port resolution fails closed when USB enumeration raises."""
    with patch(
        "homeassistant.components.easywave.transceiver.serial.tools.list_ports.comports",
        side_effect=OSError("usb unavailable"),
    ):
        assert resolve_gateway_port(SUPPORTED_USB_IDS, usb_serial="222") is None
