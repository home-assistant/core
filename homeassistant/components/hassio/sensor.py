"""Sensor platform for Hass.io addons."""

from collections.abc import Callable
from dataclasses import dataclass

from aiohasupervisor.models.base import ContainerStats

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
from .coordinator import HassioStatsData
from .entity import (
    HassioAddonEntity,
    HassioHostEntity,
    HassioOSEntity,
    HassioStatsEntity,
)


@dataclass(frozen=True, kw_only=True)
class HassioAddonSensorEntityDescription(SensorEntityDescription):
    """Hass.io add-on sensor entity description."""

    value_fn: Callable[[HassioAddonSensor], str | None]


@dataclass(frozen=True, kw_only=True)
class HassioStatsSensorEntityDescription(SensorEntityDescription):
    """Hass.io stats sensor entity description."""

    value_fn: Callable[[HassioStatsSensor], float]


@dataclass(frozen=True, kw_only=True)
class HassioOSSensorEntityDescription(SensorEntityDescription):
    """Hass.io OS sensor entity description."""

    value_fn: Callable[[HassioOSSensor], str | None]


@dataclass(frozen=True, kw_only=True)
class HassioHostSensorEntityDescription(SensorEntityDescription):
    """Hass.io host sensor entity description."""

    value_fn: Callable[[HostSensor], str | float | None]


ADDON_ENTITY_DESCRIPTIONS = (
    HassioAddonSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="version",
        translation_key="version",
        value_fn=lambda entity: entity.addon_data.addon.version,
    ),
    HassioAddonSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="version_latest",
        translation_key="version_latest",
        value_fn=lambda entity: entity.addon_data.addon.version_latest,
    ),
)

STATS_ENTITY_DESCRIPTIONS = (
    HassioStatsSensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_CPU_PERCENT,
        translation_key="cpu_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: entity.stats.cpu_percent,
    ),
    HassioStatsSensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_MEMORY_PERCENT,
        translation_key="memory_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: entity.stats.memory_percent,
    ),
)

OS_ENTITY_DESCRIPTIONS = (
    HassioOSSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="version",
        translation_key="version",
        value_fn=lambda entity: entity.os.version,
    ),
    HassioOSSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="version_latest",
        translation_key="version_latest",
        value_fn=lambda entity: entity.os.version_latest,
    ),
)

HOST_ENTITY_DESCRIPTIONS = (
    HassioHostSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="agent_version",
        translation_key="agent_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda entity: entity.host.agent_version,
    ),
    HassioHostSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="apparmor_version",
        translation_key="apparmor_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda entity: entity.host.apparmor_version,
    ),
    HassioHostSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="disk_total",
        translation_key="disk_total",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda entity: entity.host.disk_total,
    ),
    HassioHostSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="disk_used",
        translation_key="disk_used",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda entity: entity.host.disk_used,
    ),
    HassioHostSensorEntityDescription(
        entity_registry_enabled_default=False,
        key="disk_free",
        translation_key="disk_free",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda entity: entity.host.disk_free,
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
    def stats_fn_factory(
        addon_slug: str,
    ) -> Callable[[HassioStatsData], ContainerStats | None]:
        """Return a stats_fn for the given add-on slug."""

        def stats_fn(data: HassioStatsData) -> ContainerStats | None:
            """Return the stats for the given add-on."""
            return data.addons.get(addon_slug)

        return stats_fn

    entities.extend(
        HassioStatsSensor(
            coordinator=stats_coordinator,
            entity_description=entity_description,
            container_id=addon.addon.slug,
            stats_fn=stats_fn_factory(addon.addon.slug),
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
            stats_fn=lambda data: data.core,
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
            stats_fn=lambda data: data.supervisor,
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

    entity_description: HassioAddonSensorEntityDescription

    @property
    def native_value(self) -> str | None:
        """Return native value of entity."""
        return self.entity_description.value_fn(self)


class HassioStatsSensor(HassioStatsEntity, SensorEntity):
    """Sensor to track container stats."""

    entity_description: HassioStatsSensorEntityDescription

    @property
    def native_value(self) -> float:
        """Return native value of entity."""
        return self.entity_description.value_fn(self)


class HassioOSSensor(HassioOSEntity, SensorEntity):
    """Sensor to track a Hass.io OS attribute."""

    entity_description: HassioOSSensorEntityDescription

    @property
    def native_value(self) -> str | None:
        """Return native value of entity."""
        return self.entity_description.value_fn(self)


class HostSensor(HassioHostEntity, SensorEntity):
    """Sensor to track a host attribute."""

    entity_description: HassioHostSensorEntityDescription

    @property
    def native_value(self) -> str | float | None:
        """Return native value of entity."""
        return self.entity_description.value_fn(self)
