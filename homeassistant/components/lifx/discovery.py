"""The lifx integration discovery."""
from __future__ import annotations

import asyncio

from aiolifx.aiolifx import LifxDiscovery, Light, ScanManager

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

DEFAULT_TIMEOUT = 10


async def async_discover_devices(
    hass: HomeAssistant, timeout: int = DEFAULT_TIMEOUT
) -> list[Light]:
    """Discover lifx devices."""
    broadcast_addrs = await network.async_get_ipv4_broadcast_addresses(hass)
    tasks: list[asyncio.Task] = []
    discoveries = []
    for address in broadcast_addrs:
        manager = ScanManager(str(address))
        lifx_discovery = LifxDiscovery(hass.loop, manager, broadcast_ip=str(address))
        discoveries.append(lifx_discovery)
        lifx_discovery.start()
        tasks.append(hass.loop.create_task(manager.lifx_ip()))

    (done, pending) = await asyncio.wait(tasks, timeout=timeout)

    for discovery in discoveries:
        discovery.cleanup()

    for task in pending:
        task.cancel()

    return [task.result() for task in done]


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: list[Light],
) -> None:
    """Trigger config flows for discovered devices."""
    for device in discovered_devices:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                data={CONF_HOST: device.ip_addr, CONF_MAC: device.mac_addr},
            )
        )
