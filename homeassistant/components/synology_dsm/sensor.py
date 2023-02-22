"""Support for Synology DSM sensors."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from synology_dsm.api.core.utilization import SynoCoreUtilization
from synology_dsm.api.dsm.information import SynoDSMInformation
from synology_dsm.api.storage.storage import SynoStorage

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DISKS,
    PERCENTAGE,
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from . import SynoApi
from .const import CONF_VOLUMES, DOMAIN, ENTITY_UNIT_LOAD
from .coordinator import SynologyDSMCentralUpdateCoordinator
from .entity import (
    SynologyDSMBaseEntity,
    SynologyDSMDeviceEntity,
    SynologyDSMEntityDescription,
)
from .models import SynologyDSMData


@dataclass
class SynologyDSMSensorEntityDescription(
    SensorEntityDescription, SynologyDSMEntityDescription
):
    """Describes Synology DSM sensor entity."""


UTILISATION_SENSORS: tuple[SynologyDSMSensorEntityDescription, ...] = (
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_other_load",
        name="CPU Utilization (Other)",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chip",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_user_load",
        name="CPU Utilization (User)",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chip",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_system_load",
        name="CPU Utilization (System)",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chip",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_total_load",
        name="CPU Utilization (Total)",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chip",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_1min_load",
        name="CPU Load Average (1 min)",
        native_unit_of_measurement=ENTITY_UNIT_LOAD,
        icon="mdi:chip",
        entity_registry_enabled_default=False,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_5min_load",
        name="CPU Load Average (5 min)",
        native_unit_of_measurement=ENTITY_UNIT_LOAD,
        icon="mdi:chip",
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_15min_load",
        name="CPU Load Average (15 min)",
        native_unit_of_measurement=ENTITY_UNIT_LOAD,
        icon="mdi:chip",
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_real_usage",
        name="Memory Usage (Real)",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_size",
        name="Memory Size",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_cached",
        name="Memory Cached",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_available_swap",
        name="Memory Available (Swap)",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_available_real",
        name="Memory Available (Real)",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_total_swap",
        name="Memory Total (Swap)",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_total_real",
        name="Memory Total (Real)",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="network_up",
        name="Upload Throughput",
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        icon="mdi:upload",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="network_down",
        name="Download Throughput",
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        icon="mdi:download",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)
STORAGE_VOL_SENSORS: tuple[SynologyDSMSensorEntityDescription, ...] = (
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_status",
        name="Status",
        icon="mdi:checkbox-marked-circle-outline",
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_size_total",
        name="Total Size",
        native_unit_of_measurement=UnitOfInformation.TERABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:chart-pie",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_size_used",
        name="Used Space",
        native_unit_of_measurement=UnitOfInformation.TERABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:chart-pie",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_percentage_used",
        name="Volume Used",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-pie",
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_disk_temp_avg",
        name="Average Disk Temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_disk_temp_max",
        name="Maximum Disk Temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)
STORAGE_DISK_SENSORS: tuple[SynologyDSMSensorEntityDescription, ...] = (
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="disk_smart_status",
        name="Status (Smart)",
        icon="mdi:checkbox-marked-circle-outline",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="disk_status",
        name="Status",
        icon="mdi:checkbox-marked-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="disk_temp",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

INFORMATION_SENSORS: tuple[SynologyDSMSensorEntityDescription, ...] = (
    SynologyDSMSensorEntityDescription(
        api_key=SynoDSMInformation.API_KEY,
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoDSMInformation.API_KEY,
        key="uptime",
        name="Last Boot",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Synology NAS Sensor."""
    data: SynologyDSMData = hass.data[DOMAIN][entry.unique_id]
    api = data.api
    coordinator = data.coordinator_central

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


class SynoDSMSensor(
    SynologyDSMBaseEntity[SynologyDSMCentralUpdateCoordinator], SensorEntity
):
    """Mixin for sensor specific attributes."""

    entity_description: SynologyDSMSensorEntityDescription

    def __init__(
        self,
        api: SynoApi,
        coordinator: SynologyDSMCentralUpdateCoordinator,
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
        if self.native_unit_of_measurement == UnitOfInformation.MEGABYTES:
            return round(attr / 1024.0**2, 1)

        # Network
        if self.native_unit_of_measurement == UnitOfDataRate.KILOBYTES_PER_SECOND:
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
        coordinator: SynologyDSMCentralUpdateCoordinator,
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
        if self.native_unit_of_measurement == UnitOfInformation.TERABYTES:
            return round(attr / 1024.0**4, 2)

        return attr


class SynoDSMInfoSensor(SynoDSMSensor):
    """Representation a Synology information sensor."""

    def __init__(
        self,
        api: SynoApi,
        coordinator: SynologyDSMCentralUpdateCoordinator,
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
