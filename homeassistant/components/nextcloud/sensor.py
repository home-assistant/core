"""Summary data from Nextcoud."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator
from .entity import NextcloudEntity

SENSORS = (
    "nextcloud_system_version",
    "nextcloud_system_theme",
    "nextcloud_system_memcache.local",
    "nextcloud_system_memcache.distributed",
    "nextcloud_system_memcache.locking",
    "nextcloud_system_freespace",
    "nextcloud_system_cpuload",
    "nextcloud_system_mem_total",
    "nextcloud_system_mem_free",
    "nextcloud_system_swap_total",
    "nextcloud_system_swap_free",
    "nextcloud_system_apps_num_installed",
    "nextcloud_system_apps_num_updates_available",
    "nextcloud_system_apps_app_updates_calendar",
    "nextcloud_system_apps_app_updates_contacts",
    "nextcloud_system_apps_app_updates_tasks",
    "nextcloud_system_apps_app_updates_twofactor_totp",
    "nextcloud_storage_num_users",
    "nextcloud_storage_num_files",
    "nextcloud_storage_num_storages",
    "nextcloud_storage_num_storages_local",
    "nextcloud_storage_num_storages_home",
    "nextcloud_storage_num_storages_other",
    "nextcloud_shares_num_shares",
    "nextcloud_shares_num_shares_user",
    "nextcloud_shares_num_shares_groups",
    "nextcloud_shares_num_shares_link",
    "nextcloud_shares_num_shares_mail",
    "nextcloud_shares_num_shares_room",
    "nextcloud_shares_num_shares_link_no_password",
    "nextcloud_shares_num_fed_shares_sent",
    "nextcloud_shares_num_fed_shares_received",
    "nextcloud_shares_permissions_3_1",
    "nextcloud_server_webserver",
    "nextcloud_server_php_version",
    "nextcloud_server_php_memory_limit",
    "nextcloud_server_php_max_execution_time",
    "nextcloud_server_php_upload_max_filesize",
    "nextcloud_database_type",
    "nextcloud_database_version",
    "nextcloud_activeUsers_last5minutes",
    "nextcloud_activeUsers_last1hour",
    "nextcloud_activeUsers_last24hours",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nextcloud sensors."""
    coordinator: NextcloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NextcloudSensor(coordinator, name, entry)
            for name in coordinator.data
            if name in SENSORS
        ]
    )


class NextcloudSensor(NextcloudEntity, SensorEntity):
    """Represents a Nextcloud sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state for this sensor."""
        return self.coordinator.data.get(self.item)
