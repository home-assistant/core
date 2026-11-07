"""Thin Home Assistant wrapper around easywave_home_control.EasywaveGateway.

Protocol handling lives in easywave-home-control. Reconnection is owned by the
integration coordinator. Configured RF devices are independent of a specific
RX11; port resolution prefers the setup stick but accepts any compatible
replacement when it is the only one present.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
import contextlib
from dataclasses import dataclass
import logging
from typing import Any

from easywave_home_control import (
    EasywaveGateway,
    GatewayCallbacks,
    GatewayConfig,
    GatewayInfo,
)
from easywave_home_control.codec import EwbRcvEvent
from serialx import list_serial_ports

from homeassistant.core import HomeAssistant

from .const import (
    CONF_DEVICE_PATH,
    CONF_USB_SERIAL_NUMBER,
    SUPPORTED_USB_IDS,
    normalized_usb_serial,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GatewayPort:
    """RX11 port visible to setup and reconnect, including an ESPHome proxy."""

    device: str
    vid: int
    pid: int
    serial_number: str | None
    manufacturer: str | None


def _usb_id(value: int | str | None) -> int | None:
    """Return a USB id as an int. Scan results use hex strings."""
    if value is None:
        return None
    if isinstance(value, str):
        return int(value, 16)
    return value


def _gateway_port(port: Any) -> GatewayPort | None:
    """Normalize a serialx or USB-scan port that carries a VID and PID."""
    vid = _usb_id(getattr(port, "vid", None))
    pid = _usb_id(getattr(port, "pid", None))
    device = getattr(port, "device", None)
    if vid is None or pid is None or not isinstance(device, str):
        return None
    return GatewayPort(
        device=device,
        vid=vid,
        pid=pid,
        serial_number=getattr(port, "serial_number", None),
        manufacturer=getattr(port, "manufacturer", None),
    )


def _compatible_ports(
    raw_ports: Iterable[Any],
    usb_ids: frozenset[tuple[int, int]],
) -> list[GatewayPort]:
    """Keep the first port for each device path that matches ``usb_ids``."""
    ports: list[GatewayPort] = []
    seen: set[str] = set()
    for raw in raw_ports:
        port = raw if isinstance(raw, GatewayPort) else _gateway_port(raw)
        if port is None or port.device in seen or (port.vid, port.pid) not in usb_ids:
            continue
        seen.add(port.device)
        ports.append(port)
    return ports


async def async_list_gateway_ports(hass: HomeAssistant) -> list[GatewayPort]:
    """Return compatible RX11 ports from the Home Assistant USB scan.

    That scan includes local USB devices and ESPHome proxy ports whose firmware
    reports a USB identity. Without the USB integration, fall back to the local
    serialx enumeration.
    """
    from homeassistant.components import usb  # noqa: PLC0415

    if usb.DOMAIN in hass.config.components:
        try:
            scanned = await usb.async_scan_serial_ports(hass)
        except OSError:
            return []
        return _compatible_ports(scanned, SUPPORTED_USB_IDS)
    try:
        listed = await hass.async_add_executor_job(list_serial_ports)
    except OSError:
        return []
    return _compatible_ports(listed, SUPPORTED_USB_IDS)


def resolve_gateway_port(
    usb_ids: frozenset[tuple[int, int]],
    *,
    usb_serial: str | None = None,
    device_path: str | None = None,
    allow_replacement: bool = True,
    ports: Sequence[Any] | None = None,
) -> str | None:
    """Return the serial port for an RX11 gateway.

    Prefers the configured USB serial or device path. ``ports`` may include an
    ``esphome-hass://`` URL from the USB scan. When the configured hardware is
    absent and ``allow_replacement`` is true, the sole remaining compatible
    stick is accepted so a replacement RX11 can be used without reconfiguration.
    """
    if ports is None:
        try:
            raw_ports: Sequence[Any] = list(list_serial_ports())
        except OSError:
            return None
    else:
        raw_ports = ports

    matched = _compatible_ports(raw_ports, usb_ids)

    if usb_serial:
        for port in matched:
            if port.serial_number == usb_serial:
                return port.device

    if device_path:
        for port in matched:
            if port.device != device_path:
                continue
            # When a serial is configured, do not claim a path that already
            # belongs to a different serialized RX11 (paths can be reused).
            if usb_serial and port.serial_number and port.serial_number != usb_serial:
                continue
            return port.device

    if allow_replacement and len(matched) == 1:
        if usb_serial or device_path:
            _LOGGER.warning(
                "Configured RX11 %s is unavailable; using the only other compatible stick on %s",
                usb_serial or device_path,
                matched[0].device,
            )
        return matched[0].device

    return None


class RX11Transceiver:
    """Thin Home Assistant wrapper around easywave_home_control.EasywaveGateway."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: Mapping[str, Any] | None = None,
        *,
        device_path: str | None = None,
        allow_replacement: bool = True,
    ) -> None:
        """Initialize the RX11 gateway wrapper."""
        self.hass = hass
        config = config or {}
        self._usb_serial = normalized_usb_serial(config.get(CONF_USB_SERIAL_NUMBER))
        self._configured_path = config.get(CONF_DEVICE_PATH) or device_path
        self._allow_replacement = allow_replacement
        self._disconnect_callback: Callable[[], None] | None = None
        self._connected_callback: Callable[[], None] | None = None
        self._gateway = self._build_gateway(None)

    def _build_gateway(self, port: str | None) -> EasywaveGateway:
        """Create a gateway instance for the resolved serial port."""
        return EasywaveGateway(
            GatewayConfig(
                transceiver_id="RX11",
                port=port,
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
        port = resolve_gateway_port(
            SUPPORTED_USB_IDS,
            usb_serial=self._usb_serial,
            device_path=self._configured_path,
            allow_replacement=self._allow_replacement,
            ports=await async_list_gateway_ports(self.hass),
        )
        # Recreate the gateway with the resolved port via the public config API.
        old_gateway = self._gateway
        self._gateway = self._build_gateway(port)
        with contextlib.suppress(OSError, TimeoutError):
            await old_gateway.stop()
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
        """Reconnect to the RX11 transceiver.

        The gateway is rebuilt in STOPPED state by `_prepare_connection()`, and
        the library's `reconnect()` rejects that state — so call `connect()`.
        """
        if not await self._prepare_connection():
            return False
        return await self._gateway.connect()

    async def receive_telegram(
        self, timeout: float | None = None
    ) -> EwbRcvEvent | None:
        """Wait for an EW/EWneo telegram.

        ``timeout=None`` waits until a telegram arrives or the listen is cancelled.
        """
        return await self._gateway.ew.receive_ex(timeout=timeout)

    async def cancel_pending_receives(self) -> None:
        """Cancel pending receive requests on the hardware."""
        await self._gateway.cancel_pending_receives()
