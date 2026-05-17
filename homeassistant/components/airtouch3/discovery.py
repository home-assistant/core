"""Local discovery for AirTouch 3 controllers."""

import asyncio
from dataclasses import asdict, dataclass
import ipaddress
import logging
import socket

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery_flow

from .const import (
    DISCOVERY_ATTEMPTS,
    DISCOVERY_MESSAGE,
    DISCOVERY_PORT,
    DISCOVERY_SEND_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_DISCOVERY_LOCK = asyncio.Lock()


@dataclass(slots=True, frozen=True)
class AirTouch3Discovery:
    """Discovered AirTouch 3 controller."""

    host: str
    mac: str
    model: str


def _parse_discovery_payload(data: bytes) -> AirTouch3Discovery | None:
    """Parse an AirTouch 3 UDP discovery reply."""
    try:
        payload = data.decode("ascii").strip("\x00\r\n ")
    except UnicodeDecodeError:
        return None

    parts = [part.strip() for part in payload.split(",")]
    if len(parts) != 3:
        return None

    host, mac, model = parts
    if model != "AirTouch3":
        return None

    try:
        ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError:
        return None

    return AirTouch3Discovery(host=host, mac=mac, model=model)


async def _async_get_discovery_targets(hass: HomeAssistant) -> list[str]:
    """Return IPv4 broadcast targets for AirTouch 3 discovery."""
    targets = {
        str(broadcast_address)
        for broadcast_address in await network.async_get_ipv4_broadcast_addresses(hass)
    }

    for adapter in await network.async_get_adapters(hass):
        if not adapter["enabled"]:
            _LOGGER.debug(
                "Skipping disabled AirTouch 3 discovery adapter %s with IPv4 %s",
                adapter["name"],
                ", ".join(
                    f"{ip_info['address']}/{ip_info['network_prefix']}"
                    for ip_info in adapter["ipv4"]
                )
                or "none",
            )
            continue
        for ip_info in adapter["ipv4"]:
            interface = ipaddress.ip_interface(
                f"{ip_info['address']}/{ip_info['network_prefix']}"
            )
            broadcast = str(interface.network.broadcast_address)
            _LOGGER.debug(
                "AirTouch 3 discovery adapter %s has IPv4 %s/%s and broadcast %s",
                adapter["name"],
                ip_info["address"],
                ip_info["network_prefix"],
                broadcast,
            )
            targets.add(broadcast)

    return sorted(targets)


async def async_discover_devices(
    hass: HomeAssistant, timeout: int
) -> list[AirTouch3Discovery]:
    """Discover AirTouch 3 controllers on local IPv4 networks."""
    if _DISCOVERY_LOCK.locked():
        _LOGGER.debug("Waiting for in-progress AirTouch 3 discovery scan to finish")

    async with _DISCOVERY_LOCK:
        return await _async_discover_devices(hass, timeout)


async def _async_discover_devices(
    hass: HomeAssistant, timeout: int
) -> list[AirTouch3Discovery]:
    """Discover AirTouch 3 controllers on local IPv4 networks."""
    targets = await _async_get_discovery_targets(hass)
    if not targets:
        _LOGGER.debug("No AirTouch 3 discovery broadcast targets are available")
        return []

    _LOGGER.debug(
        "Starting AirTouch 3 discovery on UDP port %s with targets: %s",
        DISCOVERY_PORT,
        ", ".join(targets),
    )
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setblocking(False)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", DISCOVERY_PORT))
    except OSError as err:
        sock.close()
        _LOGGER.debug("Unable to bind AirTouch 3 discovery socket: %s", err)
        return []

    _LOGGER.debug("AirTouch 3 discovery socket bound to %s", sock.getsockname())
    discoveries: dict[str, AirTouch3Discovery] = {}
    try:
        for attempt in range(DISCOVERY_ATTEMPTS):
            _LOGGER.debug(
                "Sending AirTouch 3 discovery request %s/%s",
                attempt + 1,
                DISCOVERY_ATTEMPTS,
            )
            for target in targets:
                try:
                    await loop.sock_sendto(
                        sock, DISCOVERY_MESSAGE, (target, DISCOVERY_PORT)
                    )
                    _LOGGER.debug(
                        "Sent AirTouch 3 discovery request to %s:%s",
                        target,
                        DISCOVERY_PORT,
                    )
                except OSError as err:
                    _LOGGER.debug(
                        "AirTouch 3 discovery send to %s failed: %s", target, err
                    )
            if attempt < DISCOVERY_ATTEMPTS - 1:
                await asyncio.sleep(DISCOVERY_SEND_INTERVAL)

        _LOGGER.debug(
            "Listening for AirTouch 3 discovery replies for %s seconds", timeout
        )
        deadline = loop.time() + timeout
        while (remaining := deadline - loop.time()) > 0:
            try:
                data, addr = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, 512), remaining
                )
            except TimeoutError:
                break
            except OSError as err:
                _LOGGER.debug("AirTouch 3 discovery receive failed: %s", err)
                break

            if data == DISCOVERY_MESSAGE:
                _LOGGER.debug(
                    "Ignoring AirTouch 3 discovery echo from %s:%s",
                    addr[0],
                    addr[1],
                )
                continue

            if discovery := _parse_discovery_payload(data):
                _LOGGER.debug(
                    "Discovered AirTouch 3 controller at %s from %s:%s "
                    "(mac=%s, model=%s)",
                    discovery.host,
                    addr[0],
                    addr[1],
                    discovery.mac,
                    discovery.model,
                )
                discoveries[discovery.host] = discovery
                continue

            _LOGGER.debug(
                "Ignoring non-AirTouch 3 discovery payload from %s:%s: %r",
                addr[0],
                addr[1],
                data,
            )
    finally:
        sock.close()

    _LOGGER.debug(
        "AirTouch 3 discovery finished; found %s controller(s): %s",
        len(discoveries),
        ", ".join(discoveries) or "none",
    )
    return list(discoveries.values())


@callback
def async_trigger_discovery(
    hass: HomeAssistant, discovered_devices: list[AirTouch3Discovery]
) -> None:
    """Trigger config flows for discovered controllers."""
    _LOGGER.debug(
        "Triggering AirTouch 3 discovery flows for %s controller(s)",
        len(discovered_devices),
    )
    for device in discovered_devices:
        _LOGGER.debug(
            "Triggering AirTouch 3 discovery flow for %s (mac=%s)",
            device.host,
            device.mac,
        )
        discovery_flow.async_create_flow(
            hass,
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=asdict(device),
        )
