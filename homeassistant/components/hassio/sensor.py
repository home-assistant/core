"""Sensor platform for Hass.io addons."""

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
    CORE_CONTAINER,
    MAIN_COORDINATOR,
    STATS_COORDINATOR,
    SUPERVISOR_CONTAINER,
)
from .coordinator import StatsDataKey
from .entity import (
    HassioAddonEntity,
    HassioHostEntity,
    HassioOSEntity,
    HassioStatsEntity,
)

ADDON_ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key="version",
        translation_key="version",
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key="version_latest",
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

OS_ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key="version",
        translation_key="version",
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key="version_latest",
        translation_key="version_latest",
    ),
)

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
        for addon in addons_coordinator.data.addons.values()
        for entity_description in ADDON_ENTITY_DESCRIPTIONS
    )

    # Add-on stats sensors (cpu_percent, memory_percent)
    entities.extend(
        HassioStatsSensor(
            coordinator=stats_coordinator,
            entity_description=entity_description,
            container_id=addon.addon.slug,
            data_key=StatsDataKey.ADDONS,
            device_id=addon.addon.slug,
            unique_id_prefix=addon.addon.slug,
        )
        for addon in addons_coordinator.data.addons.values()
        for entity_description in STATS_ENTITY_DESCRIPTIONS
    )

    # Core stats sensors
    entities.extend(
        HassioStatsSensor(
            coordinator=stats_coordinator,
            entity_description=entity_description,
            container_id=CORE_CONTAINER,
            data_key=StatsDataKey.CORE,
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
            data_key=StatsDataKey.SUPERVISOR,
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
    def native_value(self) -> str | None:
        """Return native value of entity."""
        return getattr(
            self.coordinator.data.addons[self._addon_slug].addon,
            self.entity_description.key,
        )


class HassioStatsSensor(HassioStatsEntity, SensorEntity):
    """Sensor to track container stats."""

    @property
    def native_value(self) -> float:
        """Return native value of entity."""
        assert self._stats is not None
        return getattr(self._stats, self.entity_description.key)


class HassioOSSensor(HassioOSEntity, SensorEntity):
    """Sensor to track a Hass.io OS attribute."""

    @property
    def native_value(self) -> str | None:
        """Return native value of entity."""
        assert self.coordinator.data.os is not None
        return getattr(self.coordinator.data.os, self.entity_description.key)


class HostSensor(HassioHostEntity, SensorEntity):
    """Sensor to track a host attribute."""

    @property
    def native_value(self) -> str | float | None:
        """Return native value of entity."""
        return getattr(self.coordinator.data.host, self.entity_description.key)
