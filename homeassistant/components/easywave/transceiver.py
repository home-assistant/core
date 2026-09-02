"""Thin Home Assistant wrapper around easywave_home_control.EasywaveGateway.

Protocol handling lives in easywave-home-control. Reconnection is owned by the
integration coordinator. Configured RF devices are independent of a specific
RX11; port resolution prefers the setup stick but accepts any compatible
replacement when it is the only one present.
"""

from collections.abc import Callable, Mapping
from functools import partial
import logging
from typing import Any

from easywave_home_control import (
    EasywaveGateway,
    GatewayCallbacks,
    GatewayConfig,
    GatewayInfo,
)
from easywave_home_control.codec import EwbRcvEvent
import serial.tools.list_ports

from homeassistant.core import HomeAssistant

from .const import (
    CONF_DEVICE_PATH,
    CONF_USB_SERIAL_NUMBER,
    SUPPORTED_USB_IDS,
    normalized_usb_serial,
)

_LOGGER = logging.getLogger(__name__)


def resolve_gateway_port(
    usb_ids: frozenset[tuple[int, int]],
    *,
    usb_serial: str | None = None,
    device_path: str | None = None,
) -> str | None:
    """Return the serial port for an RX11 gateway.

    Prefers the configured USB serial or device path. When that hardware is
    absent, any sole compatible stick is accepted so a replacement RX11 can be
    used without reconfiguration.
    """
    try:
        ports = [
            port
            for port in serial.tools.list_ports.comports()
            if port.vid is not None
            and port.pid is not None
            and (port.vid, port.pid) in usb_ids
        ]
    except OSError:
        return None

    if usb_serial:
        for port in ports:
            if port.serial_number == usb_serial:
                return port.device

    if device_path:
        for port in ports:
            if port.device == device_path:
                return port.device

    if len(ports) == 1:
        if usb_serial or device_path:
            _LOGGER.debug(
                "Configured RX11 unavailable, using sole compatible stick on %s",
                ports[0].device,
            )
        return ports[0].device

    return None


class RX11Transceiver:
    """Thin Home Assistant wrapper around easywave_home_control.EasywaveGateway."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: Mapping[str, Any] | None = None,
        *,
        device_path: str | None = None,
    ) -> None:
        """Initialize the RX11 gateway wrapper."""
        self.hass = hass
        config = config or {}
        self._usb_serial = normalized_usb_serial(config.get(CONF_USB_SERIAL_NUMBER))
        self._configured_path = config.get(CONF_DEVICE_PATH) or device_path
        self._disconnect_callback: Callable[[], None] | None = None
        self._connected_callback: Callable[[], None] | None = None
        self._gateway = EasywaveGateway(
            GatewayConfig(
                transceiver_id="RX11",
                port=None,
                usb_ids=SUPPORTED_USB_IDS,
                auto_reconnect=False,
                auto_listen=False,
            ),
            callbacks=GatewayCallbacks(
                on_connected=self._notify_connected,
                on_disconnected=self._notify_disconnect,
            ),
        )

    @property
    def is_connected(self) -> bool:
        """Return whether the gateway is connected."""
        return self._gateway.is_connected

    @property
    def device_path(self) -> str | None:
        """Return the serial device path."""
        return self._gateway.device_path

    @property
    def usb_serial_number(self) -> str | None:
        """Return the USB serial number of the connected stick."""
        return self._gateway.usb_serial_number

    @property
    def hw_version(self) -> str | None:
        """Return the hardware version reported by the transceiver."""
        return self._gateway.hw_version

    @property
    def fw_version(self) -> str | None:
        """Return the firmware version reported by the transceiver."""
        return self._gateway.fw_version

    def set_disconnect_callback(self, callback: Callable[[], None] | None) -> None:
        """Register a callback for connection loss."""
        self._disconnect_callback = callback

    def set_connected_callback(self, callback: Callable[[], None] | None) -> None:
        """Register a callback for successful connection."""
        self._connected_callback = callback

    def _notify_connected(self, _info: GatewayInfo) -> None:
        """Forward library connect events to the integration callback."""
        if not self._connected_callback:
            return
        try:
            self.hass.loop.call_soon_threadsafe(self._connected_callback)
        except (OSError, RuntimeError) as err:
            _LOGGER.error("Error in connected callback: %s", err)

    def _notify_disconnect(self) -> None:
        """Forward library disconnect events to the integration callback."""
        if not self._disconnect_callback:
            return
        try:
            self.hass.loop.call_soon_threadsafe(self._disconnect_callback)
        except (OSError, RuntimeError) as err:
            _LOGGER.error("Error in disconnect callback: %s", err)

    async def _prepare_connection(self) -> bool:
        """Resolve the configured gateway port before connecting."""
        port = await self.hass.async_add_executor_job(
            partial(
                resolve_gateway_port,
                SUPPORTED_USB_IDS,
                usb_serial=self._usb_serial,
                device_path=self._configured_path,
            )
        )
        self._gateway._config.port = port  # noqa: SLF001
        # Library connect() uses _device_path; config.port alone is ignored.
        self._gateway._device_path = port  # noqa: SLF001
        return port is not None

    async def connect(self) -> bool:
        """Connect to the RX11 transceiver."""
        if not await self._prepare_connection():
            return False
        return await self._gateway.connect()

    async def disconnect(self) -> None:
        """Disconnect from the RX11 transceiver."""
        await self._gateway.disconnect()

    async def dispose(self) -> None:
        """Stop the gateway and release resources."""
        await self._gateway.stop()

    async def reconnect(self) -> bool:
        """Reconnect to the RX11 transceiver."""
        if not await self._prepare_connection():
            return False
        return await self._gateway.reconnect()

    async def receive_telegram(self, timeout: float = 30.0) -> EwbRcvEvent | None:
        """Wait for an EW/EWneo telegram."""
        return await self._gateway.ew.receive_ex(timeout=timeout)

    async def cancel_pending_receives(self) -> None:
        """Cancel pending receive requests on the hardware."""
        await self._gateway.cancel_pending_receives()
