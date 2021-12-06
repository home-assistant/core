"""The Flux LED/MagicLight integration discovery."""
from __future__ import annotations

import asyncio
import logging

from flux_led.aioscanner import AIOBulbScanner
from flux_led.const import ATTR_ID, ATTR_IPADDR, ATTR_MODEL, ATTR_MODEL_DESCRIPTION
from flux_led.scanner import FluxLEDDiscovery, merge_discoveries

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.core import HomeAssistant, callback

from .const import DISCOVER_SCAN_TIMEOUT, DOMAIN, FLUX_LED_DISCOVERY_LOCK

_LOGGER = logging.getLogger(__name__)


@callback
def async_name_from_discovery(device: FluxLEDDiscovery) -> str:
    """Convert a flux_led discovery to a human readable name."""
    mac_address = device[ATTR_ID]
    if mac_address is None:
        return device[ATTR_IPADDR]
    short_mac = mac_address[-6:]
    if device[ATTR_MODEL_DESCRIPTION]:
        return f"{device[ATTR_MODEL_DESCRIPTION]} {short_mac}"
    return f"{device[ATTR_MODEL]} {short_mac}"


async def async_discover_devices(
    hass: HomeAssistant, timeout: int, address: str | None = None
) -> list[FluxLEDDiscovery]:
    """Discover flux led devices."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if FLUX_LED_DISCOVERY_LOCK not in domain_data:
        domain_data[FLUX_LED_DISCOVERY_LOCK] = asyncio.Lock()
    async with domain_data[FLUX_LED_DISCOVERY_LOCK]:
        return await _async_discover_devices(hass, timeout, address)


async def _async_discover_devices(
    hass: HomeAssistant, timeout: int, address: str | None = None
) -> list[FluxLEDDiscovery]:
    """Discover flux led devices under a lock."""
    if address:
        targets = [address]
    else:
        targets = [
            str(address)
            for address in await network.async_get_ipv4_broadcast_addresses(hass)
        ]

    merged_discovery: dict[str, FluxLEDDiscovery] = {}
    for idx, discovered in enumerate(
        await asyncio.gather(
            *[
                AIOBulbScanner().async_scan(timeout=timeout, address=address)
                for address in targets
            ],
            return_exceptions=True,
        )
    ):
        if isinstance(discovered, Exception):
            _LOGGER.debug("Scanning %s failed with error: %s", targets[idx], discovered)
            continue
        assert isinstance(discovered, list)
        for device in discovered:
            if existing := merged_discovery.get(device[ATTR_IPADDR]):
                merge_discoveries(existing, device)
            else:
                merged_discovery[device[ATTR_IPADDR]] = device
    return list(merged_discovery.values())


async def async_discover_device(
    hass: HomeAssistant, host: str
) -> FluxLEDDiscovery | None:
    """Direct discovery at a single ip instead of broadcast."""
    # If we are missing the unique_id we should be able to fetch it
    # from the device by doing a directed discovery at the host only
    for device in await async_discover_devices(hass, DISCOVER_SCAN_TIMEOUT, host):
        if device[ATTR_IPADDR] == host:
            return device
    return None


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: list[FluxLEDDiscovery],
) -> None:
    """Trigger config flows for discovered devices."""
    for device in discovered_devices:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_DISCOVERY},
                data={**device},
            )
        )
