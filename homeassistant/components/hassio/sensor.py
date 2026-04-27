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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ADDONS_COORDINATOR,
    ATTR_CPU_PERCENT,
    ATTR_MEMORY_PERCENT,
    ATTR_SLUG,
    ATTR_VERSION,
    ATTR_VERSION_LATEST,
    CORE_CONTAINER,
    DATA_KEY_ADDONS,
    DATA_KEY_CORE,
    DATA_KEY_HOST,
    DATA_KEY_OS,
    DATA_KEY_SUPERVISOR,
    MAIN_COORDINATOR,
    STATS_COORDINATOR,
    SUPERVISOR_CONTAINER,
)
from .entity import (
    HassioAddonEntity,
    HassioHostEntity,
    HassioOSEntity,
    HassioStatsEntity,
)

COMMON_ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_VERSION,
        translation_key="version",
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_VERSION_LATEST,
        translation_key="version_latest",
    ),
)

STATS_ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_CPU_PERCENT,
        translation_key="cpu_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_MEMORY_PERCENT,
        translation_key="memory_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

OS_ENTITY_DESCRIPTIONS = COMMON_ENTITY_DESCRIPTIONS

HOST_ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key="agent_version",
        translation_key="agent_version",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key="apparmor_version",
        translation_key="apparmor_version",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key="disk_total",
        translation_key="disk_total",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key="disk_used",
        translation_key="disk_used",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key="disk_free",
        translation_key="disk_free",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Sensor set up for Hass.io config entry."""
    addons_coordinator = hass.data[ADDONS_COORDINATOR]
    coordinator = hass.data[MAIN_COORDINATOR]
    stats_coordinator = hass.data[STATS_COORDINATOR]

    entities: list[SensorEntity] = []

    # Add-on non-stats sensors (version, version_latest)
    entities.extend(
        HassioAddonSensor(
            addon=addon,
            coordinator=addons_coordinator,
            entity_description=entity_description,
        )
        for addon in addons_coordinator.data[DATA_KEY_ADDONS].values()
        for entity_description in COMMON_ENTITY_DESCRIPTIONS
    )

    # Add-on stats sensors (cpu_percent, memory_percent)
    entities.extend(
        HassioStatsSensor(
            coordinator=stats_coordinator,
            entity_description=entity_description,
            container_id=addon[ATTR_SLUG],
            data_key=DATA_KEY_ADDONS,
            device_id=addon[ATTR_SLUG],
            unique_id_prefix=addon[ATTR_SLUG],
        )
        for addon in addons_coordinator.data[DATA_KEY_ADDONS].values()
        for entity_description in STATS_ENTITY_DESCRIPTIONS
    )

    # Core stats sensors
    entities.extend(
        HassioStatsSensor(
            coordinator=stats_coordinator,
            entity_description=entity_description,
            container_id=CORE_CONTAINER,
            data_key=DATA_KEY_CORE,
            device_id="core",
            unique_id_prefix="home_assistant_core",
        )
        for entity_description in STATS_ENTITY_DESCRIPTIONS
    )

    # Supervisor stats sensors
    entities.extend(
        HassioStatsSensor(
            coordinator=stats_coordinator,
            entity_description=entity_description,
            container_id=SUPERVISOR_CONTAINER,
            data_key=DATA_KEY_SUPERVISOR,
            device_id="supervisor",
            unique_id_prefix="home_assistant_supervisor",
        )
        for entity_description in STATS_ENTITY_DESCRIPTIONS
    )

    # Host sensors
    entities.extend(
        HostSensor(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in HOST_ENTITY_DESCRIPTIONS
    )

    # OS sensors
    if coordinator.is_hass_os:
        entities.extend(
            HassioOSSensor(
                coordinator=coordinator,
                entity_description=entity_description,
            )
            for entity_description in OS_ENTITY_DESCRIPTIONS
        )

    async_add_entities(entities)


class HassioAddonSensor(HassioAddonEntity, SensorEntity):
    """Sensor to track a Hass.io add-on attribute."""

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[DATA_KEY_ADDONS][self._addon_slug][
            self.entity_description.key
        ]


class HassioStatsSensor(HassioStatsEntity, SensorEntity):
    """Sensor to track container stats."""

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        if self._data_key == DATA_KEY_ADDONS:
            return self.coordinator.data[DATA_KEY_ADDONS][self._container_id][
                self.entity_description.key
            ]
        return self.coordinator.data[self._data_key][self.entity_description.key]


class HassioOSSensor(HassioOSEntity, SensorEntity):
    """Sensor to track a Hass.io OS attribute."""

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[DATA_KEY_OS][self.entity_description.key]


class HostSensor(HassioHostEntity, SensorEntity):
    """Sensor to track a host attribute."""

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[DATA_KEY_HOST][self.entity_description.key]
