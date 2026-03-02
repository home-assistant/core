"""Internal discovery service for iZone AC."""

from datetime import timedelta
import logging

import aiohttp
import pizone

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DATA_DISCOVERY_SERVICE,
    DISPATCH_CONTROLLER_DISCONNECTED,
    DISPATCH_CONTROLLER_DISCOVERED,
    DISPATCH_CONTROLLER_RECONNECTED,
    DISPATCH_CONTROLLER_UPDATE,
    DISPATCH_ZONE_UPDATE,
    STATIC_RECONNECT_INTERVAL,
    TIMEOUT_CONNECT,
)

_LOGGER = logging.getLogger(__name__)


class DiscoveryService(pizone.Listener):
    """Discovery data and interfacing with pizone library."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise discovery service."""
        super().__init__()
        self.hass = hass
        self.pi_disco: pizone.DiscoveryService | None = None
        # Track static-IP controllers and their keepalive unsub callbacks
        self._static_hosts: dict[str, str] = {}  # device_uid -> host
        self._keepalive_unsub: CALLBACK_TYPE | None = None

    # Listener interface
    def controller_discovered(self, ctrl: pizone.Controller) -> None:
        """Handle new controller discovery."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_DISCOVERED, ctrl)

    def controller_disconnected(self, ctrl: pizone.Controller, ex: Exception) -> None:
        """On disconnect from controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_DISCONNECTED, ctrl, ex)

    def controller_reconnected(self, ctrl: pizone.Controller) -> None:
        """On reconnect to controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_RECONNECTED, ctrl)

    def controller_update(self, ctrl: pizone.Controller) -> None:
        """System update message is received from the controller."""
        async_dispatcher_send(self.hass, DISPATCH_CONTROLLER_UPDATE, ctrl)

    def zone_update(self, ctrl: pizone.Controller, zone: pizone.Zone) -> None:
        """Zone update message is received from the controller."""
        async_dispatcher_send(self.hass, DISPATCH_ZONE_UPDATE, ctrl, zone)

    def _track_static_controller(
        self, device_uid: str, host: str, ctrl: pizone.Controller
    ) -> None:
        """Track a static-IP controller and refresh its address.

        Updates the controller's address and starts the keepalive
        mechanism if not already running.
        """
        ctrl._refresh_address(host)  # noqa: SLF001
        self._static_hosts[device_uid] = host
        self._start_keepalive()

    async def async_register_controller(
        self, host: str, device_uid: str
    ) -> pizone.Controller:
        """Register a controller by IP address.

        If the controller is already known, updates its address.
        Otherwise creates, initializes, and registers a new controller.
        """
        assert self.pi_disco is not None

        # Check if controller is already discovered
        if device_uid in self.pi_disco.controllers:
            ctrl = self.pi_disco.controllers[device_uid]
            self._track_static_controller(device_uid, host, ctrl)
            return ctrl

        # Create controller via the pizone library internals
        controller = pizone.Controller(
            self.pi_disco,
            device_uid=device_uid,
            device_ip=host,
            is_v2=False,
            is_ipower=False,
        )
        await controller._initialize()  # noqa: SLF001

        # Register it in the discovery service
        self.pi_disco.controllers[device_uid] = controller
        self.pi_disco.controller_discovered(controller)

        self._track_static_controller(device_uid, host, controller)
        return controller

    def _start_keepalive(self) -> None:
        """Start periodic keepalive for static-IP controllers.

        The pizone library relies on UDP broadcast responses to trigger
        reconnection after a connection failure. Since broadcasts don't
        cross VLANs, we periodically call _refresh_address on static-IP
        controllers to simulate the broadcast response and trigger the
        library's built-in retry logic.
        """
        if self._keepalive_unsub is not None:
            return  # Already running

        async def _keepalive_tick(_now) -> None:
            """Periodic keepalive for static-IP controllers."""
            if not self.pi_disco:
                return
            for device_uid, host in self._static_hosts.items():
                ctrl = self.pi_disco.controllers.get(device_uid)
                if ctrl is None:
                    continue
                # If controller has a pending failure, poke _refresh_address
                # to trigger the library's _retry_connection logic
                if ctrl._fail_exception is not None:  # noqa: SLF001
                    _LOGGER.debug(
                        "Keepalive: triggering reconnect for %s at %s",
                        device_uid,
                        host,
                    )
                    ctrl._refresh_address(host)  # noqa: SLF001

        self._keepalive_unsub = async_track_time_interval(
            self.hass,
            _keepalive_tick,
            timedelta(seconds=STATIC_RECONNECT_INTERVAL),
        )

    def stop_keepalive(self) -> None:
        """Stop the periodic keepalive."""
        if self._keepalive_unsub is not None:
            self._keepalive_unsub()
            self._keepalive_unsub = None


async def async_start_discovery_service(hass: HomeAssistant):
    """Set up the pizone internal discovery."""
    if disco := hass.data.get(DATA_DISCOVERY_SERVICE):
        # Already started
        return disco
    _LOGGER.debug("Starting iZone Discovery Service")

    # discovery local services
    disco = DiscoveryService(hass)
    hass.data[DATA_DISCOVERY_SERVICE] = disco

    # Start the pizone discovery service, disco is the listener
    session = aiohttp_client.async_get_clientsession(hass)
    disco.pi_disco = pizone.discovery(disco, session=session)
    await disco.pi_disco.start_discovery()

    return disco


async def async_stop_discovery_service(hass: HomeAssistant):
    """Stop the discovery service."""
    if not (disco := hass.data.get(DATA_DISCOVERY_SERVICE)):
        return

    disco.stop_keepalive()
    await disco.pi_disco.close()
    del hass.data[DATA_DISCOVERY_SERVICE]

    _LOGGER.debug("Stopped iZone Discovery Service")


async def async_get_device_uid(hass: HomeAssistant, host: str) -> str:
    """Query an iZone device at the given IP address and return its UID.

    Raises ConnectionError if the device cannot be reached or doesn't
    respond with valid iZone system settings.
    """
    session = aiohttp_client.async_get_clientsession(hass)
    try:
        async with session.get(
            f"http://{host}/SystemSettings",
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_CONNECT),
        ) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)
            device_uid = data.get("AirStreamDeviceUId")
            if not device_uid:
                raise ConnectionError(
                    "Device did not return a valid AirStreamDeviceUId"
                )
            return device_uid
    except (
        aiohttp.ClientError,
        TimeoutError,
        KeyError,
        TypeError,
        ValueError,
    ) as ex:
        raise ConnectionError(f"Unable to connect to iZone device at {host}") from ex


async def async_add_controller_by_ip(
    hass: HomeAssistant, host: str, device_uid: str | None = None
) -> pizone.Controller:
    """Manually add a controller by IP address.

    If device_uid is provided, skips the HTTP lookup to avoid a redundant
    network call (the UID is already known from config flow validation).
    """
    disco = await async_start_discovery_service(hass)

    if device_uid is None:
        device_uid = await async_get_device_uid(hass, host)

    return await disco.async_register_controller(host, device_uid)
