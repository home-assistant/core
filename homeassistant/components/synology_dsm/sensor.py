"""Support for Synology DSM sensors."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DISKS,
    DATA_MEGABYTES,
    DATA_RATE_KILOBYTES_PER_SECOND,
    DATA_TERABYTES,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.temperature import display_temp
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import utcnow

from . import SynoApi, SynologyDSMBaseEntity, SynologyDSMDeviceEntity
from .const import (
    CONF_VOLUMES,
    COORDINATOR_CENTRAL,
    DOMAIN,
    ENTITY_UNIT_LOAD,
    INFORMATION_SENSORS,
    STORAGE_DISK_SENSORS,
    STORAGE_VOL_SENSORS,
    SYNO_API,
    TEMP_SENSORS_KEYS,
    UTILISATION_SENSORS,
    EntityInfo,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Synology NAS Sensor."""

    data = hass.data[DOMAIN][entry.unique_id]
    api: SynoApi = data[SYNO_API]
    coordinator = data[COORDINATOR_CENTRAL]

    entities: list[SynoDSMUtilSensor | SynoDSMStorageSensor | SynoDSMInfoSensor] = [
        SynoDSMUtilSensor(api, sensor_type, sensor, coordinator)
        for sensor_type, sensor in UTILISATION_SENSORS.items()
    ]

    # Handle all volumes
    if api.storage.volumes_ids:
        for volume in entry.data.get(CONF_VOLUMES, api.storage.volumes_ids):
            entities += [
                SynoDSMStorageSensor(
                    api,
                    sensor_type,
                    sensor,
                    coordinator,
                    volume,
                )
                for sensor_type, sensor in STORAGE_VOL_SENSORS.items()
            ]

    # Handle all disks
    if api.storage.disks_ids:
        for disk in entry.data.get(CONF_DISKS, api.storage.disks_ids):
            entities += [
                SynoDSMStorageSensor(
                    api,
                    sensor_type,
                    sensor,
                    coordinator,
                    disk,
                )
                for sensor_type, sensor in STORAGE_DISK_SENSORS.items()
            ]

    entities += [
        SynoDSMInfoSensor(api, sensor_type, sensor, coordinator)
        for sensor_type, sensor in INFORMATION_SENSORS.items()
    ]

    async_add_entities(entities)


class SynoDSMSensor(SynologyDSMBaseEntity):
    """Mixin for sensor specific attributes."""

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        if self.entity_type in TEMP_SENSORS_KEYS:
            return self.hass.config.units.temperature_unit
        return self._unit


class SynoDSMUtilSensor(SynoDSMSensor, SensorEntity):
    """Representation a Synology Utilisation sensor."""

    @property
    def state(self) -> Any | None:
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

        # CPU load average
        if self._unit == ENTITY_UNIT_LOAD:
            return round(attr / 100, 2)

        return attr

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._api.utilisation)


class SynoDSMStorageSensor(SynologyDSMDeviceEntity, SynoDSMSensor, SensorEntity):
    """Representation a Synology Storage sensor."""

    @property
    def state(self) -> Any | None:
        """Return the state."""
        attr = getattr(self._api.storage, self.entity_type)(self._device_id)
        if attr is None:
            return None

        # Data (disk space)
        if self._unit == DATA_TERABYTES:
            return round(attr / 1024.0 ** 4, 2)

        # Temperature
        if self.entity_type in TEMP_SENSORS_KEYS:
            return display_temp(self.hass, attr, TEMP_CELSIUS, PRECISION_TENTHS)

        return attr


class SynoDSMInfoSensor(SynoDSMSensor, SensorEntity):
    """Representation a Synology information sensor."""

    def __init__(
        self,
        api: SynoApi,
        entity_type: str,
        entity_info: EntityInfo,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]],
    ) -> None:
        """Initialize the Synology SynoDSMInfoSensor entity."""
        super().__init__(api, entity_type, entity_info, coordinator)
        self._previous_uptime: str | None = None
        self._last_boot: str | None = None

    @property
    def state(self) -> Any | None:
        """Return the state."""
        attr = getattr(self._api.information, self.entity_type)
        if attr is None:
            return None

        # Temperature
        if self.entity_type in TEMP_SENSORS_KEYS:
            return display_temp(self.hass, attr, TEMP_CELSIUS, PRECISION_TENTHS)

        if self.entity_type == "uptime":
            # reboot happened or entity creation
            if self._previous_uptime is None or self._previous_uptime > attr:
                last_boot = utcnow() - timedelta(seconds=attr)
                self._last_boot = last_boot.replace(microsecond=0).isoformat()

            self._previous_uptime = attr
            return self._last_boot
        return attr
