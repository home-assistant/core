"""Summary data from Nextcoud."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Final, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfInformation,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator
from .entity import NextcloudEntity

UNIT_OF_LOAD: Final[str] = "load"

SENSORS: Final[dict[str, SensorEntityDescription]] = {
    "activeUsers_last1hour": SensorEntityDescription(
        key="activeUsers_last1hour",
        translation_key="activeusers_last1hour",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:account-multiple",
    ),
    "activeUsers_last24hours": SensorEntityDescription(
        key="activeUsers_last24hours",
        translation_key="activeusers_last24hours",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:account-multiple",
    ),
    "activeUsers_last5minutes": SensorEntityDescription(
        key="activeUsers_last5minutes",
        translation_key="activeusers_last5minutes",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:account-multiple",
    ),
    "cache_expunges": SensorEntityDescription(
        key="cache_expunges",
        translation_key="cache_expunges",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache_mem_size": SensorEntityDescription(
        key="cache_mem_size",
        translation_key="cache_mem_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "cache_memory_type": SensorEntityDescription(
        key="cache_memory_type",
        translation_key="cache_memory_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache_num_entries": SensorEntityDescription(
        key="cache_num_entries",
        translation_key="cache_num_entries",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache_num_hits": SensorEntityDescription(
        key="cache_num_hits",
        translation_key="cache_num_hits",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache_num_inserts": SensorEntityDescription(
        key="cache_num_inserts",
        translation_key="cache_num_inserts",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache_num_misses": SensorEntityDescription(
        key="cache_num_misses",
        translation_key="cache_num_misses",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache_num_slots": SensorEntityDescription(
        key="cache_num_slots",
        translation_key="cache_num_slots",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache_start_time": SensorEntityDescription(
        key="cache_start_time",
        translation_key="cache_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "cache_ttl": SensorEntityDescription(
        key="cache_ttl",
        translation_key="cache_ttl",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "database_size": SensorEntityDescription(
        key="database_size",
        translation_key="database_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:database",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "database_type": SensorEntityDescription(
        key="database_type",
        translation_key="database_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:database",
    ),
    "database_version": SensorEntityDescription(
        key="database_version",
        translation_key="database_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:database",
    ),
    "interned_strings_usage_buffer_size": SensorEntityDescription(
        key="interned_strings_usage_buffer_size",
        translation_key="interned_strings_usage_buffer_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "interned_strings_usage_free_memory": SensorEntityDescription(
        key="interned_strings_usage_free_memory",
        translation_key="interned_strings_usage_free_memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "interned_strings_usage_number_of_strings": SensorEntityDescription(
        key="interned_strings_usage_number_of_strings",
        translation_key="interned_strings_usage_number_of_strings",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "interned_strings_usage_used_memory": SensorEntityDescription(
        key="interned_strings_usage_used_memory",
        translation_key="interned_strings_usage_used_memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "jit_buffer_free": SensorEntityDescription(
        key="jit_buffer_free",
        translation_key="jit_buffer_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "jit_buffer_size": SensorEntityDescription(
        key="jit_buffer_size",
        translation_key="jit_buffer_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "jit_kind": SensorEntityDescription(
        key="jit_kind",
        translation_key="jit_kind",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "jit_opt_flags": SensorEntityDescription(
        key="jit_opt_flags",
        translation_key="jit_opt_flags",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "jit_opt_level": SensorEntityDescription(
        key="jit_opt_level",
        translation_key="jit_opt_level",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics_blacklist_miss_ratio": SensorEntityDescription(
        key="opcache_statistics_blacklist_miss_ratio",
        translation_key="opcache_statistics_blacklist_miss_ratio",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "opcache_statistics_blacklist_misses": SensorEntityDescription(
        key="opcache_statistics_blacklist_misses",
        translation_key="opcache_statistics_blacklist_misses",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics_hash_restarts": SensorEntityDescription(
        key="opcache_statistics_hash_restarts",
        translation_key="opcache_statistics_hash_restarts",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics_hits": SensorEntityDescription(
        key="opcache_statistics_hits",
        translation_key="opcache_statistics_hits",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics_last_restart_time": SensorEntityDescription(
        key="opcache_statistics_last_restart_time",
        translation_key="opcache_statistics_last_restart_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics_manual_restarts": SensorEntityDescription(
        key="opcache_statistics_manual_restarts",
        translation_key="opcache_statistics_manual_restarts",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics_max_cached_keys": SensorEntityDescription(
        key="opcache_statistics_max_cached_keys",
        translation_key="opcache_statistics_max_cached_keys",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics_misses": SensorEntityDescription(
        key="opcache_statistics_misses",
        translation_key="opcache_statistics_misses",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics_num_cached_keys": SensorEntityDescription(
        key="opcache_statistics_num_cached_keys",
        translation_key="opcache_statistics_num_cached_keys",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics_num_cached_scripts": SensorEntityDescription(
        key="opcache_statistics_num_cached_scripts",
        translation_key="opcache_statistics_num_cached_scripts",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics_oom_restarts": SensorEntityDescription(
        key="opcache_statistics_oom_restarts",
        translation_key="opcache_statistics_oom_restarts",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "opcache_statistics_opcache_hit_rate": SensorEntityDescription(
        key="opcache_statistics_opcache_hit_rate",
        translation_key="opcache_statistics_opcache_hit_rate",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
    ),
    "opcache_statistics_start_time": SensorEntityDescription(
        key="opcache_statistics_start_time",
        translation_key="opcache_statistics_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "server_php_opcache_memory_usage_current_wasted_percentage": SensorEntityDescription(
        key="server_php_opcache_memory_usage_current_wasted_percentage",
        translation_key="server_php_opcache_memory_usage_current_wasted_percentage",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:language-php",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
    ),
    "server_php_opcache_memory_usage_free_memory": SensorEntityDescription(
        key="server_php_opcache_memory_usage_free_memory",
        translation_key="server_php_opcache_memory_usage_free_memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "server_php_opcache_memory_usage_used_memory": SensorEntityDescription(
        key="server_php_opcache_memory_usage_used_memory",
        translation_key="server_php_opcache_memory_usage_used_memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "server_php_opcache_memory_usage_wasted_memory": SensorEntityDescription(
        key="server_php_opcache_memory_usage_wasted_memory",
        translation_key="server_php_opcache_memory_usage_wasted_memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "server_php_max_execution_time": SensorEntityDescription(
        key="server_php_max_execution_time",
        translation_key="server_php_max_execution_time",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
    "server_php_memory_limit": SensorEntityDescription(
        key="server_php_memory_limit",
        translation_key="server_php_memory_limit",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "server_php_upload_max_filesize": SensorEntityDescription(
        key="server_php_upload_max_filesize",
        translation_key="server_php_upload_max_filesize",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "server_php_version": SensorEntityDescription(
        key="server_php_version",
        translation_key="server_php_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:language-php",
    ),
    "server_webserver": SensorEntityDescription(
        key="server_webserver",
        translation_key="server_webserver",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares_num_fed_shares_sent": SensorEntityDescription(
        key="shares_num_fed_shares_sent",
        translation_key="shares_num_fed_shares_sent",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares_num_fed_shares_received": SensorEntityDescription(
        key="shares_num_fed_shares_received",
        translation_key="shares_num_fed_shares_received",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares_num_shares": SensorEntityDescription(
        key="shares_num_shares",
        translation_key="shares_num_shares",
    ),
    "shares_num_shares_groups": SensorEntityDescription(
        key="shares_num_shares_groups",
        translation_key="shares_num_shares_groups",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares_num_shares_link": SensorEntityDescription(
        key="shares_num_shares_link",
        translation_key="shares_num_shares_link",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares_num_shares_link_no_password": SensorEntityDescription(
        key="shares_num_shares_link_no_password",
        translation_key="shares_num_shares_link_no_password",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares_num_shares_mail": SensorEntityDescription(
        key="shares_num_shares_mail",
        translation_key="shares_num_shares_mail",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares_num_shares_room": SensorEntityDescription(
        key="shares_num_shares_room",
        translation_key="shares_num_shares_room",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "shares_num_shares_user": SensorEntityDescription(
        key="server_num_shares_user",
        translation_key="shares_num_shares_user",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "sma_avail_mem": SensorEntityDescription(
        key="sma_avail_mem",
        translation_key="sma_avail_mem",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "sma_num_seg": SensorEntityDescription(
        key="sma_num_seg",
        translation_key="sma_num_seg",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "sma_seg_size": SensorEntityDescription(
        key="sma_seg_size",
        translation_key="sma_seg_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    "storage_num_files": SensorEntityDescription(
        key="storage_num_files",
        translation_key="storage_num_files",
    ),
    "storage_num_storages": SensorEntityDescription(
        key="storage_num_storages",
        translation_key="storage_num_storages",
    ),
    "storage_num_storages_home": SensorEntityDescription(
        key="storage_num_storages_home",
        translation_key="storage_num_storages_home",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "storage_num_storages_local": SensorEntityDescription(
        key="storage_num_storages_local",
        translation_key="storage_num_storages_local",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "storage_num_storages_other": SensorEntityDescription(
        key="storage_num_storages_other",
        translation_key="storage_num_storages_other",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "storage_num_users": SensorEntityDescription(
        key="storage_num_users",
        translation_key="storage_num_users",
    ),
    "system_apps_num_installed": SensorEntityDescription(
        key="system_apps_num_installed",
        translation_key="system_apps_num_installed",
    ),
    "system_apps_num_updates_available": SensorEntityDescription(
        key="system_apps_num_updates_available",
        translation_key="system_apps_num_updates_available",
        icon="mdi:update",
    ),
    "system_cpuload_1": SensorEntityDescription(
        key="system_cpuload_1",
        translation_key="system_cpuload_1",
        native_unit_of_measurement=UNIT_OF_LOAD,
        icon="mdi:chip",
        suggested_display_precision=2,
    ),
    "system_cpuload_5": SensorEntityDescription(
        key="system_cpuload_5",
        translation_key="system_cpuload_5",
        native_unit_of_measurement=UNIT_OF_LOAD,
        icon="mdi:chip",
        suggested_display_precision=2,
    ),
    "system_cpuload_15": SensorEntityDescription(
        key="system_cpuload_15",
        translation_key="system_cpuload_15",
        native_unit_of_measurement=UNIT_OF_LOAD,
        icon="mdi:chip",
        suggested_display_precision=2,
    ),
    "system_freespace": SensorEntityDescription(
        key="system_freespace",
        translation_key="system_freespace",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:harddisk",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    "system_mem_free": SensorEntityDescription(
        key="system_mem_free",
        translation_key="system_mem_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    "system_mem_total": SensorEntityDescription(
        key="system_mem_total",
        translation_key="system_mem_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    "system_memcache.distributed": SensorEntityDescription(
        key="system_memcache.distributed",
        translation_key="system_memcache_distributed",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "system_memcache.local": SensorEntityDescription(
        key="system_memcache.local",
        translation_key="system_memcache_local",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "system_memcache.locking": SensorEntityDescription(
        key="system_memcache.locking",
        translation_key="system_memcache_locking",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "system_swap_total": SensorEntityDescription(
        key="system_swap_total",
        translation_key="system_swap_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    "system_swap_free": SensorEntityDescription(
        key="system_swap_free",
        translation_key="system_swap_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    "system_theme": SensorEntityDescription(
        key="system_theme",
        translation_key="system_theme",
    ),
    "system_version": SensorEntityDescription(
        key="system_version",
        translation_key="system_version",
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
            return datetime.fromtimestamp(cast(int, val), tz=UTC)
        return val
