"""Shared identity and bounded discovery for Gree devices."""

import asyncio
from typing import Any

from greeclimate.device import DeviceInfo
from greeclimate.discovery import Discovery

from homeassistant.components.network import async_get_ipv4_broadcast_addresses
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton
from homeassistant.util.hass_dict import HassKey

from .const import CONF_IDENTIFIER, DISCOVERY_TIMEOUT

DATA_DISCOVERY: HassKey[DiscoveryService] = HassKey("gree_discovery")


def normalize_identifier(identifier: str) -> str:
    """Normalize a reported identifier without changing its public spelling."""
    if not isinstance(identifier, str) or not (
        normalized := identifier.replace(":", "")
        .replace("-", "")
        .replace(".", "")
        .lower()
    ):
        raise ValueError("Gree device identifier must be a nonempty string")
    return normalized


def device_info_to_data(info: DeviceInfo) -> dict[str, Any]:
    """Return the persisted discovery metadata, excluding session state."""
    return {
        "host": info.ip,
        "port": info.port,
        CONF_IDENTIFIER: info.mac,
        "name": info.name,
        "brand": info.brand,
        "model": info.model,
        "version": info.version,
        "mid": info.mid,
    }


@singleton(DATA_DISCOVERY)
@callback
def async_get_discovery(hass: HomeAssistant) -> DiscoveryService:
    """Return the domain-wide scanner."""
    return DiscoveryService(hass)


class DiscoveryService:
    """Serialize fresh scans without owning device connections or enrollment."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the scanner."""
        self.hass = hass
        self._scan_lock = asyncio.Lock()
        self._discovery: Discovery | None = None
        self._stopped = False

    async def async_scan(
        self, *, wait_for: int = DISCOVERY_TIMEOUT
    ) -> dict[str, DeviceInfo]:
        """Return only observations from this bounded scan."""
        async with self._scan_lock:
            if self._stopped or self.hass.is_stopping:
                return {}
            discovery = self._discovery = Discovery(DISCOVERY_TIMEOUT)
            try:
                targets = list(await async_get_ipv4_broadcast_addresses(self.hass))
                if not targets or self._stopped or self.hass.is_stopping:
                    return {}
                devices = await discovery.scan(
                    wait_for=wait_for, target_addresses=targets
                )
                if self._stopped or self.hass.is_stopping:
                    return {}
                return {normalize_identifier(info.mac): info for info in devices}
            finally:
                if self._discovery is discovery:
                    self._discovery = None
                discovery.close()

    @callback
    def async_stop(self) -> None:
        """Close active discovery and prevent subsequent scans."""
        self._stopped = True
        if self._discovery is not None:
            discovery, self._discovery = self._discovery, None
            discovery.close()
