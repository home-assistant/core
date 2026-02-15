"""Sensor exposing last successful Cloudflare DDNS update time and external IP."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CloudflareConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CloudflareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cloudflare sensors."""
    coordinator = entry.runtime_data
    zone = coordinator.zone

    entities: list[SensorEntity] = [
        CloudflareLastUpdateSensor(
            coordinator=coordinator,
            entry=entry,
            zone_id=zone["id"],
            zone_name=zone["name"],
        ),
        CloudflareExternalIpSensor(
            coordinator=coordinator,
            entry=entry,
            zone_id=zone["id"],
            zone_name=zone["name"],
        ),
    ]
    async_add_entities(entities)


class CloudflareBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor with common device info for zone."""

    def __init__(
        self, coordinator, entry: ConfigEntry, zone_id: str, zone_name: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._zone_id = zone_id
        self._zone_name = zone_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone_id)},
            name=f"Cloudflare Zone {zone_name}",
            manufacturer="Cloudflare",
            model="DNS Zone",
        )


class CloudflareLastUpdateSensor(CloudflareBaseSensor):
    """Sensor showing the timestamp of last successful update."""

    _attr_has_entity_name = True
    _attr_name = "Last Update"
    _attr_unique_id = "cloudflare_last_update_{zone}"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, coordinator, entry: ConfigEntry, zone_id: str, zone_name: str
    ) -> None:
        """Initialize the Last Update sensor."""
        super().__init__(coordinator, entry, zone_id, zone_name)
        self._attr_unique_id = f"{zone_id}_last_update"

    @property
    def native_value(self) -> datetime | None:
        """Return the last update time."""
        data: dict[str, Any] | None = self.coordinator.data
        if not data:
            return None
        return data.get("updated_at")


class CloudflareExternalIpSensor(CloudflareBaseSensor):
    """Sensor showing current external IP used for DDNS."""

    _attr_has_entity_name = True
    _attr_name = "External IP"
    _attr_unique_id = "cloudflare_external_ip_{zone}"
    _attr_device_class = None

    def __init__(
        self, coordinator, entry: ConfigEntry, zone_id: str, zone_name: str
    ) -> None:
        """Initialize the External IP sensor."""
        super().__init__(coordinator, entry, zone_id, zone_name)
        self._attr_unique_id = f"{zone_id}_external_ip"

    @property
    def native_value(self) -> str | None:
        """Return the external IP."""
        data: dict[str, Any] | None = self.coordinator.data
        if not data:
            return None
        return data.get("external_ip")
