"""Local discovery for AirTouch 3 controllers."""

import asyncio
from dataclasses import asdict
import ipaddress
import logging

from pyairtouch3 import AirTouch3Discovery, async_discover_targets

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery_flow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_DISCOVERY_LOCK = asyncio.Lock()


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

    return await async_discover_targets(targets, timeout, logger=_LOGGER)


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
