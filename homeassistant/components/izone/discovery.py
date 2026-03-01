"""Internal discovery service for  iZone AC."""

import logging

import aiohttp
import pizone

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DATA_DISCOVERY_SERVICE,
    DISPATCH_CONTROLLER_DISCONNECTED,
    DISPATCH_CONTROLLER_DISCOVERED,
    DISPATCH_CONTROLLER_RECONNECTED,
    DISPATCH_CONTROLLER_UPDATE,
    DISPATCH_ZONE_UPDATE,
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
            data = await response.json(content_type=None)
            device_uid = data.get("AirStreamDeviceUId")
            if not device_uid:
                raise ConnectionError(
                    "Device did not return a valid AirStreamDeviceUId"
                )
            return device_uid
    except (aiohttp.ClientError, TimeoutError, KeyError, TypeError) as ex:
        raise ConnectionError(
            f"Unable to connect to iZone device at {host}"
        ) from ex


async def async_add_controller_by_ip(
    hass: HomeAssistant, host: str
) -> pizone.Controller:
    """Manually add a controller by IP address.

    This queries the device for its UID, creates a Controller instance,
    initialises it, and registers it with the discovery service.
    """
    disco = await async_start_discovery_service(hass)

    device_uid = await async_get_device_uid(hass, host)

    # Check if controller is already discovered
    if device_uid in disco.pi_disco.controllers:
        ctrl = disco.pi_disco.controllers[device_uid]
        # Update IP in case it changed
        ctrl._refresh_address(host)  # noqa: SLF001
        return ctrl

    # Create controller via the pizone library internals
    controller = pizone.Controller(
        disco.pi_disco,
        device_uid=device_uid,
        device_ip=host,
        is_v2=False,
        is_ipower=False,
    )
    await controller._initialize()  # noqa: SLF001

    # Register it in the discovery service
    disco.pi_disco.controllers[device_uid] = controller
    disco.pi_disco.controller_discovered(controller)

    return controller
