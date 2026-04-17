"""Local Push receiver for Wibeee energy monitors.

Registers HTTP views within Home Assistant's built-in web server to receive
push data from WiBeee devices. The device sends periodic GET requests to
fixed paths:
  - /Wibeee/receiverAvg   (average data - main endpoint)
  - /Wibeee/receiver      (instantaneous data)
  - /Wibeee/receiverLeap  (gradient data)

These paths are hardcoded in the WiBeee firmware and cannot be changed.
The device must be configured to point to the HA instance IP and port
(typically 8123).

This module uses HomeAssistantView with ``requires_auth = False`` because
the WiBeee device has no ability to send authentication tokens.

The PushReceiver is a singleton stored in ``hass.data[DOMAIN]``.  Each
config entry registers its MAC address so incoming push data is routed
to the correct sensor entities.

Documentation: https://github.com/fquinto/pywibeee
"""

from __future__ import annotations

from collections.abc import Callable
import logging

from aiohttp.web import Request, Response

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PUSH_PARAM_TO_SENSOR, PUSH_PHASE_MAP

_LOGGER = logging.getLogger(__name__)

# Key for the singleton PushReceiver in hass.data
DATA_PUSH_RECEIVER = f"{DOMAIN}_push_receiver"

# Type alias for push data callback
PushDataCallback = Callable[[dict[str, dict[str, str]]], None]


class PushReceiver:
    """Manages push data listeners for registered WiBeee devices.

    Each device is identified by its MAC address. When push data arrives,
    the receiver parses it and calls the registered callback for that device.
    """

    def __init__(self) -> None:
        """Initialize the push receiver."""
        self._listeners: dict[str, PushDataCallback] = {}

    def register_device(self, mac_address: str, callback_fn: PushDataCallback) -> None:
        """Register a device to receive push updates."""
        mac_clean = mac_address.replace(":", "").lower()
        self._listeners[mac_clean] = callback_fn
        _LOGGER.debug(
            "Registered push listener for MAC %s (total: %d)",
            mac_clean,
            len(self._listeners),
        )

    def unregister_device(self, mac_address: str) -> None:
        """Unregister a device from push updates."""
        mac_clean = mac_address.replace(":", "").lower()
        self._listeners.pop(mac_clean, None)
        _LOGGER.debug(
            "Unregistered push listener for MAC %s (remaining: %d)",
            mac_clean,
            len(self._listeners),
        )

    def get_listener(self, mac_address: str) -> PushDataCallback | None:
        """Get the callback for a given MAC address."""
        mac_clean = mac_address.replace(":", "").lower()
        return self._listeners.get(mac_clean)

    @property
    def device_count(self) -> int:
        """Return the number of registered devices."""
        return len(self._listeners)


def parse_push_data(
    query_params: dict[str, str],
) -> dict[str, dict[str, str]]:
    """Parse push query parameters into organized phase/sensor data.

    Input: {"mac": "001ec0112232", "v1": "230.5", "a1": "277", "vt": "230.5", ...}
    Output: {
        "fase1": {"vrms": "230.5", "p_activa": "277", ...},
        "fase4": {"vrms": "230.5", ...},  # "t" suffix -> fase4 (total)
    }
    """
    phases: dict[str, dict[str, str]] = {}

    for param, value in query_params.items():
        if len(param) < 2:
            continue

        prefix = param[:-1]  # e.g. "v" from "v1"
        suffix = param[-1]  # e.g. "1" from "v1"

        # Check if this is a known sensor parameter
        sensor_key = PUSH_PARAM_TO_SENSOR.get(prefix)
        phase_key = PUSH_PHASE_MAP.get(suffix)

        if sensor_key and phase_key:
            if phase_key not in phases:
                phases[phase_key] = {}
            phases[phase_key][sensor_key] = value

    return phases


def _dispatch_push_data(receiver: PushReceiver, query: dict[str, str]) -> str:
    """Dispatch push data to the correct device listener.

    Returns a log message describing what happened.
    """
    mac_addr = query.get("mac", "").replace(":", "").lower()
    if not mac_addr:
        return "no MAC in push data"

    listener = receiver.get_listener(mac_addr)
    if listener is None:
        return f"unregistered device {mac_addr}"

    parsed = parse_push_data(query)
    if parsed:
        listener(parsed)
        return (
            f"device {mac_addr}: {len(parsed)} phases, "
            f"{sum(len(v) for v in parsed.values())} values"
        )
    return f"device {mac_addr}: no recognized sensors"


class WibeeeReceiverAvgView(HomeAssistantView):
    """Handle /Wibeee/receiverAvg - the main push endpoint.

    The WiBeee device sends averaged sensor data as GET query parameters.
    Expected response: ``<<<WBAVG `` (the device checks this prefix).
    """

    url = "/Wibeee/receiverAvg"
    name = "api:wibeee:receiver_avg"
    requires_auth = False

    def __init__(self, receiver: PushReceiver) -> None:
        """Initialize with the push receiver instance."""
        self._receiver = receiver

    async def get(self, request: Request) -> Response:
        """Handle incoming averaged push data from a WiBeee device."""
        query = dict(request.query)
        result = _dispatch_push_data(self._receiver, query)
        _LOGGER.debug("receiverAvg: %s", result)
        return Response(status=200, text="<<<WBAVG ")


class WibeeeReceiverView(HomeAssistantView):
    """Handle /Wibeee/receiver - instantaneous data endpoint.

    Same data format as receiverAvg. Expected response: ``<<<WBAVG ``.
    """

    url = "/Wibeee/receiver"
    name = "api:wibeee:receiver"
    requires_auth = False

    def __init__(self, receiver: PushReceiver) -> None:
        """Initialize with the push receiver instance."""
        self._receiver = receiver

    async def get(self, request: Request) -> Response:
        """Handle incoming instantaneous push data."""
        query = dict(request.query)
        result = _dispatch_push_data(self._receiver, query)
        _LOGGER.debug("receiver: %s", result)
        return Response(status=200, text="<<<WBAVG ")


class WibeeeReceiverLeapView(HomeAssistantView):
    """Handle /Wibeee/receiverLeap - gradient data endpoint.

    Same data format. Expected response: ``<<<WGRADIENT=007 ``.
    """

    url = "/Wibeee/receiverLeap"
    name = "api:wibeee:receiver_leap"
    requires_auth = False

    def __init__(self, receiver: PushReceiver) -> None:
        """Initialize with the push receiver instance."""
        self._receiver = receiver

    async def get(self, request: Request) -> Response:
        """Handle incoming gradient push data."""
        query = dict(request.query)
        result = _dispatch_push_data(self._receiver, query)
        _LOGGER.debug("receiverLeap: %s", result)
        return Response(status=200, text="<<<WGRADIENT=007 ")


def async_setup_push_receiver(hass: HomeAssistant) -> PushReceiver:
    """Set up the push receiver and register HTTP views.

    Creates a singleton PushReceiver stored in ``hass.data`` and registers
    the three WiBeee HTTP views on HA's built-in web server.

    This is idempotent: calling it multiple times returns the same receiver.

    Args:
        hass: Home Assistant instance.

    Returns:
        The PushReceiver instance.
    """
    # Return existing receiver if already set up
    if DATA_PUSH_RECEIVER in hass.data:
        return hass.data[DATA_PUSH_RECEIVER]

    receiver = PushReceiver()

    # Register the three push endpoints on HA's HTTP server
    hass.http.register_view(WibeeeReceiverAvgView(receiver))
    hass.http.register_view(WibeeeReceiverView(receiver))
    hass.http.register_view(WibeeeReceiverLeapView(receiver))

    hass.data[DATA_PUSH_RECEIVER] = receiver

    _LOGGER.info(
        "Wibeee push receiver registered on HA HTTP server "
        "(/Wibeee/receiverAvg, /Wibeee/receiver, /Wibeee/receiverLeap)"
    )

    return receiver
