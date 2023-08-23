"""Summary data from Nextcoud."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Final, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfInformation,
    UnitOfTime,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator
from .entity import NextcloudEntity


SENSORS: Final[dict[str, SensorEntityDescription]] = {
    "activeUsers last1hour": SensorEntityDescription(
        key="activeUsers last1hour",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:account-multiple",
    ),
    "activeUsers last24hours": SensorEntityDescription(
        key="activeUsers last24hours",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:account-multiple",
    ),
    "activeUsers last5minutes": SensorEntityDescription(
        key="activeUsers last5minutes",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:account-multiple",
    ),
    "cache expunges": SensorEntityDescription(
        key="cache expunges",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache mem_size": SensorEntityDescription(
        key="cache mem_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "cache memory_type": SensorEntityDescription(
        key="cache memory_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache num_entries": SensorEntityDescription(
        key="cache num_entries",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache num_hits": SensorEntityDescription(
        key="cache num_hits",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache num_inserts": SensorEntityDescription(
        key="cache num_inserts",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache num_misses": SensorEntityDescription(
        key="cache num_misses",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache num_solts": SensorEntityDescription(
        key="cache num_solts",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache start_time": SensorEntityDescription(
        key="cache start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache ttl": SensorEntityDescription(
        key="cache ttl",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "database size": SensorEntityDescription(
        key="database size",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:database",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "database type": SensorEntityDescription(
        key="database type",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:database",
    ),
    "database version": SensorEntityDescription(
        key="database version",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:database",
    ),
    "interned_strings_usage buffer_size": SensorEntityDescription(
        key="interned_strings_usage buffer_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "interned_strings_usage free_memory": SensorEntityDescription(
        key="interned_strings_usage free_memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "interned_strings_usage number_of_strings": SensorEntityDescription(
        key="interned_strings_usage number_of_strings",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "interned_strings_usage used_memory": SensorEntityDescription(
        key="interned_strings_usage used_memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "jit buffer_free": SensorEntityDescription(
        key="jit buffer_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "jit buffer_size": SensorEntityDescription(
        key="jit buffer_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "jit kind": SensorEntityDescription(
        key="jit kind",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "jit opt_flags": SensorEntityDescription(
        key="jit opt_flags",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "jit opt_level": SensorEntityDescription(
        key="jit opt_level",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics blacklist_miss_ratio": SensorEntityDescription(
        key="opcache_statistics blacklist_miss_ratio",
        device_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "opcache_statistics blacklist_misses": SensorEntityDescription(
        key="opcache_statistics blacklist_misses",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics hash_restarts": SensorEntityDescription(
        key="opcache_statistics hash_restarts",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics hits": SensorEntityDescription(
        key="opcache_statistics hits",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics last_restart_time": SensorEntityDescription(
        key="opcache_statistics last_restart_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics manual_restarts": SensorEntityDescription(
        key="opcache_statistics manual_restarts",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics max_cached_keys": SensorEntityDescription(
        key="opcache_statistics max_cached_keys",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics misses": SensorEntityDescription(
        key="opcache_statistics misses",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics num_cached_keys": SensorEntityDescription(
        key="opcache_statistics num_cached_keys",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics num_cached_scripts": SensorEntityDescription(
        key="opcache_statistics num_cached_scripts",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics oom_restarts": SensorEntityDescription(
        key="opcache_statistics oom_restarts",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics opcache_hit_rate": SensorEntityDescription(
        key="opcache_statistics opcache_hit_rate",
        device_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
    ),
    "opcache_statistics start_time": SensorEntityDescription(
        key="opcache_statistics start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "server php opcache memory_usage current_wasted_percentage": SensorEntityDescription(
        key="server php opcache memory_usage current_wasted_percentage",
        device_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:language-php",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
    ),
    "server php opcache memory_usage free_memory": SensorEntityDescription(
        key="server php opcache memory_usage free_memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "server php opcache memory_usage used_memory": SensorEntityDescription(
        key="server php opcache memory_usage used_memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "server php opcache memory_usage wasted_memory": SensorEntityDescription(
        key="server php opcache memory_usage wasted_memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "server php max_execution_time": SensorEntityDescription(
        key="server php max_execution_time",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
    "server php memory_limit": SensorEntityDescription(
        key="server php memory_limit",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "server php upload_max_filesize": SensorEntityDescription(
        key="server php upload_max_filesize",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "server php version": SensorEntityDescription(
        key="server php version",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:language-php",
    ),
    "server webserver": SensorEntityDescription(
        key="server webserver",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares num_fed_shares_sent": SensorEntityDescription(
        key="shares num_fed_shares_sent",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares num_fed_shares_received": SensorEntityDescription(
        key="shares num_fed_shares_received",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares num_shares": SensorEntityDescription(
        key="shares num_shares",
    ),
    "shares num_shares_groups": SensorEntityDescription(
        key="shares num_shares_groups",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares num_shares_link": SensorEntityDescription(
        key="shares num_shares_link",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares num_shares_link_no_password": SensorEntityDescription(
        key="shares num_shares_link_no_password",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares num_shares_mail": SensorEntityDescription(
        key="shares num_shares_mail",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares num_shares_room": SensorEntityDescription(
        key="shares num_shares_room",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares num_shares_user": SensorEntityDescription(
        key="server num_shares_user",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "sma avail_mem": SensorEntityDescription(
        key="sma avail_mem",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "sma num_seg": SensorEntityDescription(
        key="sma num_seg",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "sma seg_size": SensorEntityDescription(
        key="sma seg_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "storage num_files": SensorEntityDescription(
        key="storage num_files",
    ),
    "storage num_storages": SensorEntityDescription(
        key="storage num_storages",
    ),
    "storage num_storages_home": SensorEntityDescription(
        key="storage num_storages_home",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "storage num_storages_local": SensorEntityDescription(
        key="storage num_storages_local",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "storage num_storages_other": SensorEntityDescription(
        key="storage num_storages_other",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "storage num_users": SensorEntityDescription(
        key="storage num_users",
    ),
    "system apps num_installed": SensorEntityDescription(
        key="system apps num_installed",
    ),
    "system apps num_updates_available": SensorEntityDescription(
        key="system apps num_updates_available", icon="mdi:update"
    ),
    "system cpuload": SensorEntityDescription(
        key="system cpuload",
        native_unit_of_measurement="",
        suggested_display_precision=3,
    ),
    "system freespace": SensorEntityDescription(
        key="system freespace",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:harddisk",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    "system mem_free": SensorEntityDescription(
        key="system mem_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    "system mem_total": SensorEntityDescription(
        key="system mem_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    "system memcache.distributed": SensorEntityDescription(
        key="system memcache.distributed",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "system memcache.local": SensorEntityDescription(
        key="system memcache.local",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "system memcache.locking": SensorEntityDescription(
        key="system memcache.locking",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "system swap_total": SensorEntityDescription(
        key="system swap_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    "system swap_free": SensorEntityDescription(
        key="system swap_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nextcloud sensors."""
    coordinator: NextcloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NextcloudSensor(coordinator, name, entry, SENSORS[name])
            for name in coordinator.data
            if name in SENSORS
        ]
    )


class NextcloudSensor(NextcloudEntity, SensorEntity):
    """Represents a Nextcloud sensor."""

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state for this sensor."""
        val = self.coordinator.data.get(self.item)
        if self.item == "system cpuload":
            return val[0] if isinstance(val, list) else None
        if (
            getattr(self.entity_description, "device_class", None)
            == SensorDeviceClass.TIMESTAMP
        ):
            return datetime.fromtimestamp(cast(int, val), tz=timezone.utc)
        return val
