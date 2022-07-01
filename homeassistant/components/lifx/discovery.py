"""The lifx integration discovery."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging

from aiolifx.aiolifx import LifxDiscovery, Light, ScanManager

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .util import get_real_mac_addr

DEFAULT_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


async def async_discover_devices(
    hass: HomeAssistant, timeout: int = DEFAULT_TIMEOUT
) -> Iterable[Light]:
    """Discover lifx devices."""
    all_lights: dict[str, Light] = {}
    broadcast_addrs = await network.async_get_ipv4_broadcast_addresses(hass)
    discoveries = []
    for address in broadcast_addrs:
        manager = ScanManager(str(address))
        lifx_discovery = LifxDiscovery(hass.loop, manager, broadcast_ip=str(address))
        discoveries.append(lifx_discovery)
        lifx_discovery.start()

    await asyncio.sleep(timeout)
    for discovery in discoveries:
        all_lights.update(discovery.lights)
        discovery.cleanup()

    return all_lights.values()


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: Iterable[Light],
) -> None:
    """Trigger config flows for discovered devices."""
    for device in discovered_devices:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                data={
                    CONF_HOST: device.ip_addr,
                    CONF_MAC: get_real_mac_addr(
                        device.mac_addr, device.host_firmware_version
                    ),
                },
            )
        )
