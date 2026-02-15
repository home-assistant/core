"""Switch entities to control Cloudflare DNS proxy (proxied flag)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_DOMAINS
from .helpers import async_update_proxied_state


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Cloudflare proxy switches for a config entry."""
    runtime = entry.runtime_data  # type: ignore[attr-defined]
    coordinator = runtime.coordinator
    zone = runtime.dns_zone
    domains: list[str] = entry.data.get(CONF_DOMAINS, [])

    entities: list[CloudflareProxySwitch] = [
        CloudflareProxySwitch(
            coordinator=coordinator,
            entry=entry,
            zone_id=zone["id"],
            zone_name=zone["name"],
            domain=domain,
            api_token=runtime.api_token,
        )
        for domain in domains
    ]

    async_add_entities(entities)


class CloudflareProxySwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a proxied state toggle for a DNS record."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        zone_id: str,
        zone_name: str,
        domain: str,
        api_token: str,
    ) -> None:
        """Initialize the Cloudflare Proxy switch."""
        super().__init__(coordinator)
        self._entry = entry
        self._zone_id = zone_id
        self._zone_name = zone_name
        self._domain = domain
        self._api_token = api_token
        self._attr_unique_id = f"{zone_id}_{domain}_proxied"
        self._attr_name = f"{domain} Proxy"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone_id)},
            name=f"Cloudflare Zone {zone_name}",
            manufacturer="Cloudflare",
            model="DNS Zone",
        )

    @property
    def _record(self) -> dict[str, Any] | None:
        data = self.coordinator.data or {}
        records = data.get("records", {})
        return records.get(self._domain)

    @property
    def is_on(self) -> bool:
        """Return True if the proxy is on."""
        record = self._record
        if not record:
            return False
        return bool(record.get("proxied"))

    async def async_turn_on(self) -> None:
        """Turn the proxy on."""
        await self._async_set_proxied(True)

    async def async_turn_off(self) -> None:
        """Turn the proxy off."""
        await self._async_set_proxied(False)

    async def _async_set_proxied(self, desired: bool) -> None:
        record = self._record
        if not record:
            # Trigger coordinator refresh to attempt creation first
            await self.coordinator.async_request_refresh()
            record = self._record
            if not record:
                return
        session = async_get_clientsession(self.hass)
        success = await async_update_proxied_state(
            session=session,
            api_token=self._api_token,
            zone_id=self._zone_id,
            record_id=record["id"],
            name=record["name"],
            content=record["content"],
            proxied=desired,
        )
        if success:
            await self.coordinator.async_request_refresh()
