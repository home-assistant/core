"""Support for Synology DSM sensors."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DISKS,
    DATA_MEGABYTES,
    DATA_RATE_KILOBYTES_PER_SECOND,
    DATA_TERABYTES,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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
    UTILISATION_SENSORS,
    SynologyDSMSensorEntityDescription,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Synology NAS Sensor."""

    data = hass.data[DOMAIN][entry.unique_id]
    api: SynoApi = data[SYNO_API]
    coordinator = data[COORDINATOR_CENTRAL]

    entities: list[SynoDSMUtilSensor | SynoDSMStorageSensor | SynoDSMInfoSensor] = [
        SynoDSMUtilSensor(api, coordinator, description)
        for description in UTILISATION_SENSORS
    ]

    # Handle all volumes
    if api.storage.volumes_ids:
        entities.extend(
            [
                SynoDSMStorageSensor(api, coordinator, description, volume)
                for volume in entry.data.get(CONF_VOLUMES, api.storage.volumes_ids)
                for description in STORAGE_VOL_SENSORS
            ]
        )

    # Handle all disks
    if api.storage.disks_ids:
        entities.extend(
            [
                SynoDSMStorageSensor(api, coordinator, description, disk)
                for disk in entry.data.get(CONF_DISKS, api.storage.disks_ids)
                for description in STORAGE_DISK_SENSORS
            ]
        )

    entities.extend(
        [
            SynoDSMInfoSensor(api, coordinator, description)
            for description in INFORMATION_SENSORS
        ]
    )

    async_add_entities(entities)


class SynoDSMSensor(SynologyDSMBaseEntity, SensorEntity):
    """Mixin for sensor specific attributes."""

    entity_description: SynologyDSMSensorEntityDescription

    def __init__(
        self,
        api: SynoApi,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]],
        description: SynologyDSMSensorEntityDescription,
    ) -> None:
        """Initialize the Synology DSM sensor entity."""
        super().__init__(api, coordinator, description)


class SynoDSMUtilSensor(SynoDSMSensor):
    """Representation a Synology Utilisation sensor."""

    @property
    def native_value(self) -> Any | None:
        """Return the state."""
        attr = getattr(self._api.utilisation, self.entity_description.key)
        if callable(attr):
            attr = attr()
        if attr is None:
            return None

        # Data (RAM)
        if self.native_unit_of_measurement == DATA_MEGABYTES:
            return round(attr / 1024.0 ** 2, 1)

        # Network
        if self.native_unit_of_measurement == DATA_RATE_KILOBYTES_PER_SECOND:
            return round(attr / 1024.0, 1)

        # CPU load average
        if self.native_unit_of_measurement == ENTITY_UNIT_LOAD:
            return round(attr / 100, 2)

        return attr

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._api.utilisation)


class SynoDSMStorageSensor(SynologyDSMDeviceEntity, SynoDSMSensor):
    """Representation a Synology Storage sensor."""

    entity_description: SynologyDSMSensorEntityDescription

    def __init__(
        self,
        api: SynoApi,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]],
        description: SynologyDSMSensorEntityDescription,
        device_id: str | None = None,
    ) -> None:
        """Initialize the Synology DSM storage sensor entity."""
        super().__init__(api, coordinator, description, device_id)

    @property
    def native_value(self) -> Any | None:
        """Return the state."""
        attr = getattr(self._api.storage, self.entity_description.key)(self._device_id)
        if attr is None:
            return None

        # Data (disk space)
        if self.native_unit_of_measurement == DATA_TERABYTES:
            return round(attr / 1024.0 ** 4, 2)

        return attr


class SynoDSMInfoSensor(SynoDSMSensor):
    """Representation a Synology information sensor."""

    def __init__(
        self,
        api: SynoApi,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]],
        description: SynologyDSMSensorEntityDescription,
    ) -> None:
        """Initialize the Synology SynoDSMInfoSensor entity."""
        super().__init__(api, coordinator, description)
        self._previous_uptime: str | None = None
        self._last_boot: datetime | None = None

    @property
    def native_value(self) -> Any | None:
        """Return the state."""
        attr = getattr(self._api.information, self.entity_description.key)
        if attr is None:
            return None

        if self.entity_description.key == "uptime":
            # reboot happened or entity creation
            if self._previous_uptime is None or self._previous_uptime > attr:
                self._last_boot = utcnow() - timedelta(seconds=attr)

            self._previous_uptime = attr
            return self._last_boot
        return attr
