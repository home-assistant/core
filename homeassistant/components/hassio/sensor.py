"""Sensor platform for Hass.io addons."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ADDONS_COORDINATOR, HassioStatsDataUpdateCoordinator
from .const import (
    ATTR_CPU_PERCENT,
    ATTR_MEMORY_PERCENT,
    ATTR_SLUG,
    ATTR_VERSION,
    ATTR_VERSION_LATEST,
    DATA_KEY_ADDONS,
    DATA_KEY_CORE,
    DATA_KEY_HOST,
    DATA_KEY_OS,
    DATA_KEY_SUPERVISOR,
    SupervisorEntityModel,
)
from .entity import (
    HassioAddonEntity,
    HassioCoreEntity,
    HassioHostEntity,
    HassioOSEntity,
    HassioSupervisorEntity,
)

COMMON_ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_VERSION,
        name="Version",
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_VERSION_LATEST,
        name="Newest version",
    ),
)

STATS_ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_CPU_PERCENT,
        name="CPU percent",
        icon="mdi:cpu-64-bit",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_MEMORY_PERCENT,
        name="Memory percent",
        icon="mdi:memory",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

ADDON_ENTITY_DESCRIPTIONS = COMMON_ENTITY_DESCRIPTIONS
OS_ENTITY_DESCRIPTIONS = COMMON_ENTITY_DESCRIPTIONS

HOST_ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key="agent_version",
        name="OS Agent version",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key="apparmor_version",
        name="Apparmor version",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key="disk_total",
        name="Disk total",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key="disk_used",
        name="Disk used",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key="disk_free",
        name="Disk free",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensor set up for Hass.io config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    entities: list[
        HassioOSSensor | HassioAddonSensor | CoreSensor | SupervisorSensor | HostSensor
    ] = []
    stats_entities: list[
        AddonStatsSensor | CoreStatsSensor | SupervisorStatsSensor
    ] = []

    for addon in coordinator.data[DATA_KEY_ADDONS].values():
        for entity_description in ADDON_ENTITY_DESCRIPTIONS:
            entities.append(
                HassioAddonSensor(
                    addon=addon,
                    coordinator=coordinator,
                    entity_description=entity_description,
                )
            )
        for entity_description in STATS_ENTITY_DESCRIPTIONS:
            stats_entities.append(
                AddonStatsSensor(
                    addon=addon,
                    coordinator=HassioStatsDataUpdateCoordinator(
                        hass=hass,
                        model=SupervisorEntityModel.ADDON,
                        addon_slug=addon[ATTR_SLUG],
                    ),
                    entity_description=entity_description,
                )
            )

    for entity_description in STATS_ENTITY_DESCRIPTIONS:
        stats_entities.append(
            CoreStatsSensor(
                coordinator=HassioStatsDataUpdateCoordinator(
                    hass=hass,
                    model=SupervisorEntityModel.CORE,
                ),
                entity_description=entity_description,
            )
        )
        stats_entities.append(
            SupervisorStatsSensor(
                coordinator=HassioStatsDataUpdateCoordinator(
                    hass=hass,
                    model=SupervisorEntityModel.SUPERVISOR,
                ),
                entity_description=entity_description,
            )
        )

    for entity_description in HOST_ENTITY_DESCRIPTIONS:
        entities.append(
            HostSensor(
                coordinator=coordinator,
                entity_description=entity_description,
            )
        )

    if coordinator.is_hass_os:
        for entity_description in OS_ENTITY_DESCRIPTIONS:
            entities.append(
                HassioOSSensor(
                    coordinator=coordinator,
                    entity_description=entity_description,
                )
            )

    async_add_entities(entities)
    async_add_entities(stats_entities, True)


class HassioAddonSensor(HassioAddonEntity, SensorEntity):
    """Sensor to track a Hass.io add-on attribute."""

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[DATA_KEY_ADDONS][self._addon_slug][
            self.entity_description.key
        ]


class HassioOSSensor(HassioOSEntity, SensorEntity):
    """Sensor to track a Hass.io add-on attribute."""

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[DATA_KEY_OS][self.entity_description.key]


class CoreSensor(HassioCoreEntity, SensorEntity):
    """Sensor to track a core attribute."""

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[DATA_KEY_CORE][self.entity_description.key]


class SupervisorSensor(HassioSupervisorEntity, SensorEntity):
    """Sensor to track a supervisor attribute."""

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[DATA_KEY_SUPERVISOR][self.entity_description.key]


class HostSensor(HassioHostEntity, SensorEntity):
    """Sensor to track a host attribute."""

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[DATA_KEY_HOST][self.entity_description.key]


class AddonStatsSensor(HassioAddonEntity, SensorEntity):
    """Sensor to track a Hass.io add-on stats attribute."""

    coordinator: HassioStatsDataUpdateCoordinator

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[self.entity_description.key]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.entity_description.key in self.coordinator.data
        )


class CoreStatsSensor(HassioCoreEntity, SensorEntity):
    """Sensor to track a Hass.io core stats attribute."""

    coordinator: HassioStatsDataUpdateCoordinator

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[self.entity_description.key]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.entity_description.key in self.coordinator.data
        )


class SupervisorStatsSensor(HassioSupervisorEntity, SensorEntity):
    """Sensor to track a Hass.io supervisor stats attribute."""

    coordinator: HassioStatsDataUpdateCoordinator

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[self.entity_description.key]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.entity_description.key in self.coordinator.data
        )
