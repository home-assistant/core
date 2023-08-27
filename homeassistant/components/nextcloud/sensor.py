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
from homeassistant.const import EntityCategory, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator
from .entity import NextcloudEntity

UNIT_OF_LOAD: Final[str] = "load"

SENSORS: Final[list[SensorEntityDescription]] = [
    SensorEntityDescription(
        key="activeUsers_last1hour",
        translation_key="nextcloud_activeusers_last1hour",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:account-multiple",
    ),
    SensorEntityDescription(
        key="activeUsers_last24hours",
        translation_key="nextcloud_activeusers_last24hours",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:account-multiple",
    ),
    SensorEntityDescription(
        key="activeUsers_last5minutes",
        translation_key="nextcloud_activeusers_last5minutes",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:account-multiple",
    ),
    SensorEntityDescription(
        key="database_type",
        translation_key="nextcloud_database_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:database",
    ),
    SensorEntityDescription(
        key="database_version",
        translation_key="nextcloud_database_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:database",
    ),
    SensorEntityDescription(
        key="server_php_max_execution_time",
        translation_key="nextcloud_server_php_max_execution_time",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
    SensorEntityDescription(
        key="server_php_memory_limit",
        translation_key="nextcloud_server_php_memory_limit",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    SensorEntityDescription(
        key="server_php_upload_max_filesize",
        translation_key="nextcloud_server_php_upload_max_filesize",
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:language-php",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=1,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
    ),
    SensorEntityDescription(
        key="server_php_version",
        translation_key="nextcloud_server_php_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:language-php",
    ),
    SensorEntityDescription(
        key="server_webserver",
        translation_key="nextcloud_server_webserver",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="shares_num_fed_shares_sent",
        translation_key="nextcloud_shares_num_fed_shares_sent",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="shares_num_fed_shares_received",
        translation_key="nextcloud_shares_num_fed_shares_received",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="shares_num_shares",
        translation_key="nextcloud_shares_num_shares",
    ),
    SensorEntityDescription(
        key="shares_num_shares_groups",
        translation_key="nextcloud_shares_num_shares_groups",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="shares_num_shares_link",
        translation_key="nextcloud_shares_num_shares_link",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="shares_num_shares_link_no_password",
        translation_key="nextcloud_shares_num_shares_link_no_password",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="shares_num_shares_mail",
        translation_key="nextcloud_shares_num_shares_mail",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="shares_num_shares_room",
        translation_key="nextcloud_shares_num_shares_room",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="server_num_shares_user",
        translation_key="nextcloud_shares_num_shares_user",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="storage_num_files",
        translation_key="nextcloud_storage_num_files",
    ),
    SensorEntityDescription(
        key="storage_num_storages",
        translation_key="nextcloud_storage_num_storages",
    ),
    SensorEntityDescription(
        key="storage_num_storages_home",
        translation_key="nextcloud_storage_num_storages_home",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="storage_num_storages_local",
        translation_key="nextcloud_storage_num_storages_local",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="storage_num_storages_other",
        translation_key="nextcloud_storage_num_storages_other",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="storage_num_users",
        translation_key="nextcloud_storage_num_users",
    ),
    SensorEntityDescription(
        key="system_apps_num_installed",
        translation_key="nextcloud_system_apps_num_installed",
    ),
    SensorEntityDescription(
        key="system_apps_num_updates_available",
        translation_key="nextcloud_system_apps_num_updates_available",
        icon="mdi:update",
    ),
    SensorEntityDescription(
        key="system_cpuload_1",
        translation_key="nextcloud_system_cpuload_1",
        native_unit_of_measurement=UNIT_OF_LOAD,
        icon="mdi:chip",
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="system_cpuload_5",
        translation_key="nextcloud_system_cpuload_5",
        native_unit_of_measurement=UNIT_OF_LOAD,
        icon="mdi:chip",
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="system_cpuload_15",
        translation_key="nextcloud_system_cpuload_15",
        native_unit_of_measurement=UNIT_OF_LOAD,
        icon="mdi:chip",
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="system_freespace",
        translation_key="nextcloud_system_freespace",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:harddisk",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    SensorEntityDescription(
        key="system_mem_free",
        translation_key="nextcloud_system_mem_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    SensorEntityDescription(
        key="system_mem_total",
        translation_key="nextcloud_system_mem_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    SensorEntityDescription(
        key="system_memcache.distributed",
        translation_key="nextcloud_system_memcache_distributed",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="system_memcache.local",
        translation_key="nextcloud_system_memcache_local",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="system_memcache.locking",
        translation_key="nextcloud_system_memcache_locking",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="system_swap_total",
        translation_key="nextcloud_system_swap_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    SensorEntityDescription(
        key="system_swap_free",
        translation_key="nextcloud_system_swap_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        suggested_display_precision=2,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    SensorEntityDescription(
        key="system_theme",
        translation_key="nextcloud_system_theme",
    ),
    SensorEntityDescription(
        key="system_version",
        translation_key="nextcloud_system_version",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nextcloud sensors."""
    coordinator: NextcloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NextcloudSensor(coordinator, entry, sensor)
            for sensor in SENSORS
            if sensor.key in coordinator.data
        ]
    )


class NextcloudSensor(NextcloudEntity, SensorEntity):
    """Represents a Nextcloud sensor."""

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state for this sensor."""
        val = self.coordinator.data.get(self.entity_description.key)
        if (
            getattr(self.entity_description, "device_class", None)
            == SensorDeviceClass.TIMESTAMP
        ):
            return datetime.fromtimestamp(cast(int, val), tz=UTC)
        return val
