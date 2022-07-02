"""The lifx integration discovery."""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Iterable
import logging
from typing import Any

from aiolifx.aiolifx import LifxDiscovery, Light, ScanManager

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 8.5


async def async_discover_devices(hass: HomeAssistant) -> Iterable[Light]:
    """Discover lifx devices."""
    all_lights: dict[str, Light] = {}
    broadcast_addrs = await network.async_get_ipv4_broadcast_addresses(hass)
    discoveries = []
    for address in broadcast_addrs:
        manager = ScanManager(str(address))
        lifx_discovery = LifxDiscovery(hass.loop, manager, broadcast_ip=str(address))
        discoveries.append(lifx_discovery)
        lifx_discovery.start()

    _LOGGER.debug("Running integration discovery with timeout: %s", DEFAULT_TIMEOUT)
    await asyncio.sleep(DEFAULT_TIMEOUT)
    for discovery in discoveries:
        all_lights.update(discovery.lights)
        discovery.cleanup()

    _LOGGER.debug("Integration discovery found: %s", all_lights)

    return all_lights.values()


@callback
def async_init_discovery_flow(
    hass: HomeAssistant, host: str
) -> Coroutine[Any, Any, FlowResult]:
    """Start discovery of devices."""
    return hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_HOST: host},
    )


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: Iterable[Light],
) -> None:
    """Trigger config flows for discovered devices."""
    for device in discovered_devices:
        hass.async_create_task(async_init_discovery_flow(hass, device.ip_addr))
