"""Support for Synology DSM sensors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

from synology_dsm.api.core.utilization import SynoCoreUtilization
from synology_dsm.api.dsm.information import SynoDSMInformation
from synology_dsm.api.storage.storage import SynoStorage

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_DISKS,
    PERCENTAGE,
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from . import SynoApi
from .const import CONF_VOLUMES, ENTITY_UNIT_LOAD
from .coordinator import SynologyDSMCentralUpdateCoordinator, SynologyDSMConfigEntry
from .entity import (
    SynologyDSMBaseEntity,
    SynologyDSMDeviceEntity,
    SynologyDSMEntityDescription,
)


@dataclass(frozen=True, kw_only=True)
class SynologyDSMSensorEntityDescription(
    SensorEntityDescription, SynologyDSMEntityDescription
):
    """Describes Synology DSM sensor entity."""


UTILISATION_SENSORS: tuple[SynologyDSMSensorEntityDescription, ...] = (
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_other_load",
        translation_key="cpu_other_load",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_user_load",
        translation_key="cpu_user_load",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_system_load",
        translation_key="cpu_system_load",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_total_load",
        translation_key="cpu_total_load",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_1min_load",
        translation_key="cpu_1min_load",
        native_unit_of_measurement=ENTITY_UNIT_LOAD,
        entity_registry_enabled_default=False,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_5min_load",
        translation_key="cpu_5min_load",
        native_unit_of_measurement=ENTITY_UNIT_LOAD,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_15min_load",
        translation_key="cpu_15min_load",
        native_unit_of_measurement=ENTITY_UNIT_LOAD,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_real_usage",
        translation_key="memory_real_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_size",
        translation_key="memory_size",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_cached",
        translation_key="memory_cached",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_available_swap",
        translation_key="memory_available_swap",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_available_real",
        translation_key="memory_available_real",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_total_swap",
        translation_key="memory_total_swap",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_total_real",
        translation_key="memory_total_real",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="network_up",
        translation_key="network_up",
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="network_down",
        translation_key="network_down",
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)
STORAGE_VOL_SENSORS: tuple[SynologyDSMSensorEntityDescription, ...] = (
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_status",
        translation_key="volume_status",
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_size_total",
        translation_key="volume_size_total",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.TERABYTES,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_size_used",
        translation_key="volume_size_used",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.TERABYTES,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_percentage_used",
        translation_key="volume_percentage_used",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_disk_temp_avg",
        translation_key="volume_disk_temp_avg",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_disk_temp_max",
        translation_key="volume_disk_temp_max",
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
        translation_key="disk_smart_status",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="disk_status",
        translation_key="disk_status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="disk_temp",
        translation_key="disk_temp",
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
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoDSMInformation.API_KEY,
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SynologyDSMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Synology NAS Sensor."""
    data = entry.runtime_data
    api = data.api
    coordinator = data.coordinator_central
    storage = api.storage
    assert storage is not None

    entities: list[SynoDSMUtilSensor | SynoDSMStorageSensor | SynoDSMInfoSensor] = [
        SynoDSMUtilSensor(api, coordinator, description)
        for description in UTILISATION_SENSORS
    ]

    # Handle all volumes
    if storage.volumes_ids:
        entities.extend(
            [
                SynoDSMStorageSensor(api, coordinator, description, volume)
                for volume in entry.data.get(CONF_VOLUMES, storage.volumes_ids)
                for description in STORAGE_VOL_SENSORS
            ]
        )

    # Handle all disks
    if storage.disks_ids:
        entities.extend(
            [
                SynoDSMStorageSensor(api, coordinator, description, disk)
                for disk in entry.data.get(CONF_DISKS, storage.disks_ids)
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
    def native_value(self) -> StateType:
        """Return the state."""
        attr = getattr(self._api.utilisation, self.entity_description.key)
        if callable(attr):
            attr = attr()

        # CPU load average
        if (
            isinstance(attr, int)
            and self.native_unit_of_measurement == ENTITY_UNIT_LOAD
        ):
            return round(attr / 100, 2)

        return attr  # type: ignore[no-any-return]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._api.utilisation) and super().available


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
    def native_value(self) -> StateType:
        """Return the state."""
        return cast(
            StateType,
            getattr(self._api.storage, self.entity_description.key)(self._device_id),
        )


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
    def native_value(self) -> StateType | datetime:
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
        return attr  # type: ignore[no-any-return]
