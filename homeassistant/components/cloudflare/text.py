"""Text entity the Cloudflare integration."""
from __future__ import annotations

from collections.abc import Mapping

from pycfdns import CloudflareException, CloudflareUpdater, DNSRecord

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up from config entry."""
    cfupdate: CloudflareUpdater = hass.data[DOMAIN][config_entry.entry_id]["client"]
    zone_id: str = hass.data[DOMAIN][config_entry.entry_id]["zone_id"]

    try:
        records = await cfupdate.get_record_info(zone_id)
    except CloudflareException as exception:
        raise PlatformNotReady from exception

    async_add_entities(
        CloudflareTextEntity(cfupdate, zone_id, entry.record) for entry in records
    )


class CloudflareTextEntity(TextEntity):
    """Representation of a demo text entity."""

    _attr_should_poll = False
    _attr_icon = "mdi:dns"

    def __init__(
        self,
        cfupdate: CloudflareUpdater,
        zone_id: str,
        record: DNSRecord,
    ) -> None:
        """Initialize the Demo text entity."""
        self._cfupdate = cfupdate
        self._zone_id = zone_id
        self._record = record
        self._attr_unique_id = record["id"]
        self._attr_name = record["name"]
        self._attr_native_value = record["content"]

    @property
    def extra_state_attributes(self) -> Mapping[str, str | bool]:
        """Return entity specific state attributes."""
        return {
            "type": self._record["type"],
            "proxied": self._record["proxied"],
        }

    async def async_set_value(self, value: str) -> None:
        """Update the value of the record."""
        update = await self._cfupdate.update_dns_record(
            zone_id=self._zone_id,
            record={**self._record, "content": value},
        )
        self._record = update["result"]
        self._attr_native_value = self._record["content"]
        self.async_write_ha_state()
