"""Support for Synology DSM binary sensors."""
from typing import Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DISKS
from homeassistant.helpers.typing import HomeAssistantType

from . import SynologyDSMEntity
from .const import DOMAIN, STORAGE_DISK_BINARY_SENSORS, SYNO_API


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Synology NAS Sensor."""

    api = hass.data[DOMAIN][entry.unique_id][SYNO_API]

    entities = []

    # Handle all disks
    if api.storage.disks_ids:
        for disk in entry.data.get(CONF_DISKS, api.storage.disks_ids):
            entities += [
                SynoNasStorageSensor(
                    api, sensor_type, STORAGE_DISK_BINARY_SENSORS[sensor_type], disk
                )
                for sensor_type in STORAGE_DISK_BINARY_SENSORS
            ]

    async_add_entities(entities)


class SynoNasStorageSensor(SynologyDSMEntity):
    """Representation a Synology Storage sensor."""

    @property
    def state(self):
        """Return the state."""
        attr = getattr(self._api.storage, self.entity_type)(self._device_id)
        if attr is None:
            return None
        return attr

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._api.information.serial, self._device_id)},
            "name": f"Synology NAS ({self._device_name} {self._device_type})",
            "manufacturer": self._device_manufacturer,
            "model": self._device_model,
            "sw_version": self._device_firmware,
            "via_device": (DOMAIN, self._api.information.serial),
        }
