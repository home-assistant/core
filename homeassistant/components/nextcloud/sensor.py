"""Summary data from Nextcoud."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN

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


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Nextcloud sensors."""
    if discovery_info is None:
        return
    sensors = []
    for name in hass.data[DOMAIN]:
        if name in SENSORS:
            sensors.append(NextcloudSensor(name))
    add_entities(sensors, True)


class NextcloudSensor(SensorEntity):
    """Represents a Nextcloud sensor."""

    def __init__(self, item):
        """Initialize the Nextcloud sensor."""
        self._name = item
        self._state = None

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return "mdi:cloud"

    @property
    def name(self):
        """Return the name for this sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state for this sensor."""
        return self._state

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return f"{self.hass.data[DOMAIN]['instance']}#{self._name}"

    def update(self) -> None:
        """Update the sensor."""
        self._state = self.hass.data[DOMAIN][self._name]
