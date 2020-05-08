"""Support for Synology DSM sensors."""
from typing import Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DISKS,
    DATA_MEGABYTES,
    DATA_RATE_KILOBYTES_PER_SECOND,
    DATA_TERABYTES,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
)
from homeassistant.helpers.temperature import display_temp
from homeassistant.helpers.typing import HomeAssistantType

from . import SynologyDSMEntity
from .const import (
    CONF_VOLUMES,
    DOMAIN,
    SECURITY_SENSORS,
    STORAGE_DISK_SENSORS,
    STORAGE_VOL_SENSORS,
    SYNO_API,
    TEMP_SENSORS_KEYS,
    UTILISATION_SENSORS,
)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Synology NAS Sensor."""

    api = hass.data[DOMAIN][entry.unique_id][SYNO_API]

    sensors = [
        SynoNasUtilSensor(api, sensor_type, UTILISATION_SENSORS[sensor_type])
        for sensor_type in UTILISATION_SENSORS
    ]

    if api.security:
        sensors += [
            SynoNasSecuritySensor(api, sensor_type, SECURITY_SENSORS[sensor_type])
            for sensor_type in SECURITY_SENSORS
        ]

    # Handle all volumes
    if api.storage.volumes_ids:
        for volume in entry.data.get(CONF_VOLUMES, api.storage.volumes_ids):
            sensors += [
                SynoNasStorageSensor(
                    api, sensor_type, STORAGE_VOL_SENSORS[sensor_type], volume
                )
                for sensor_type in STORAGE_VOL_SENSORS
            ]

    # Handle all disks
    if api.storage.disks_ids:
        for disk in entry.data.get(CONF_DISKS, api.storage.disks_ids):
            sensors += [
                SynoNasStorageSensor(
                    api, sensor_type, STORAGE_DISK_SENSORS[sensor_type], disk
                )
                for sensor_type in STORAGE_DISK_SENSORS
            ]

    async_add_entities(sensors)


class SynoNasUtilSensor(SynologyDSMEntity):
    """Representation a Synology Utilisation sensor."""

    @property
    def state(self):
        """Return the state."""
        attr = getattr(self._api.utilisation, self.entity_type)
        if callable(attr):
            attr = attr()
        if attr is None:
            return None

        # Data (RAM)
        if self._unit == DATA_MEGABYTES:
            return round(attr / 1024.0 ** 2, 1)

        # Network
        if self._unit == DATA_RATE_KILOBYTES_PER_SECOND:
            return round(attr / 1024.0, 1)

        return attr


class SynoNasStorageSensor(SynologyDSMEntity):
    """Representation a Synology Storage sensor."""

    @property
    def state(self):
        """Return the state."""
        attr = getattr(self._api.storage, self.entity_type)(self._device_id)
        if attr is None:
            return None

        # Data (disk space)
        if self._unit == DATA_TERABYTES:
            return round(attr / 1024.0 ** 4, 2)

        # Temperature
        if self.sensor_type in TEMP_SENSORS_KEYS:
            return display_temp(self.hass, attr, TEMP_CELSIUS, PRECISION_TENTHS)

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


class SynoNasSecuritySensor(SynologyDSMEntity):
    """Representation a Synology Security sensor."""

    @property
    def state(self):
        """Return the state."""
        return getattr(self._api.security, self.entity_type)

    async def async_remove(self):
        """Clean up when removing entity.

        Remove entity if no entry in entity registry exist.
        Remove entity registry entry if no entry in device registry exist.
        Remove entity registry entry if there are more than one entity linked to the device registry entry.
        """
        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        entity_entry = entity_registry.async_get(self.entity_id)
        if not entity_entry:
            await super().async_remove()
            return

        device_registry = await self.hass.helpers.device_registry.async_get_registry()
        device_entry = device_registry.async_get(entity_entry.device_id)
        if not device_entry:
            entity_registry.async_remove(self.entity_id)
            return

        entity_registry.async_remove(self.entity_id)
