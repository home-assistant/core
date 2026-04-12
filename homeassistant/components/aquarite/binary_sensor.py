"""Aquarite Binary Sensor entities."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .const import PATH_HASCD, PATH_HASCL, PATH_HASPH, PATH_HASRX
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

TANK_MODULE_PATHS = (
    "modules.ph.tank",
    "modules.rx.tank",
    "modules.cl.tank",
    "modules.cd.tank",
)

@dataclass(frozen=True)
class AquariteBinarySensorConfig:
    """Configuration for an Aquarite binary sensor."""

    translation_key: str
    value_path: str
    device_class: BinarySensorDeviceClass | None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = True


BASE_SENSORS: tuple[AquariteBinarySensorConfig, ...] = (
    AquariteBinarySensorConfig(
        "hidro_flow_status", "hidro.fl1", BinarySensorDeviceClass.PROBLEM
    ),
    AquariteBinarySensorConfig(
        "filtration_status", "filtration.status", BinarySensorDeviceClass.RUNNING
    ),
    AquariteBinarySensorConfig(
        "backwash_status", "backwash.status", BinarySensorDeviceClass.RUNNING
    ),
    AquariteBinarySensorConfig(
        "hidro_cover_reduction", "hidro.cover", BinarySensorDeviceClass.RUNNING
    ),
    AquariteBinarySensorConfig(
        "ph_pump_alarm", "modules.ph.al3", BinarySensorDeviceClass.PROBLEM
    ),
    AquariteBinarySensorConfig(
        "cd_module_installed",
        "main.hasCD",
        BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    AquariteBinarySensorConfig(
        "cl_module_installed",
        "main.hasCL",
        BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    AquariteBinarySensorConfig(
        "rx_module_installed",
        "main.hasRX",
        BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    AquariteBinarySensorConfig(
        "ph_module_installed",
        "main.hasPH",
        BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    AquariteBinarySensorConfig(
        "io_module_installed",
        "main.hasIO",
        BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    AquariteBinarySensorConfig(
        "hidro_module_installed",
        "main.hasHidro",
        BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    AquariteBinarySensorConfig(
        "ph_acid_pump", "modules.ph.pump_high_on", BinarySensorDeviceClass.RUNNING
    ),
    AquariteBinarySensorConfig(
        "ph_base_pump", "modules.ph.pump_low_on", BinarySensorDeviceClass.RUNNING
    ),
    AquariteBinarySensorConfig(
        "heating_status",
        "relays.filtration.heating.status",
        BinarySensorDeviceClass.RUNNING,
    ),
    AquariteBinarySensorConfig(
        "connected", "present", BinarySensorDeviceClass.CONNECTIVITY
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aquarite binary sensors."""
    dataservice = entry.runtime_data
    pool_id = dataservice.pool_id
    pool_name = entry.title

    entities: list[BinarySensorEntity] = [
        AquariteBinarySensorEntity(dataservice, config, pool_id, pool_name)
        for config in BASE_SENSORS
    ]

    if dataservice.get_value("main.hasCL"):
        entities.append(
            AquariteBinarySensorEntity(
                dataservice,
                AquariteBinarySensorConfig(
                    "hidro_fl2_status",
                    "hidro.fl2", BinarySensorDeviceClass.PROBLEM,
                ),
                pool_id,
                pool_name,
            )
        )
        entities.append(
            AquariteBinarySensorEntity(
                dataservice,
                AquariteBinarySensorConfig(
                    "cl_pump_status",
                    "modules.cl.pump_status", BinarySensorDeviceClass.RUNNING,
                ),
                pool_id,
                pool_name,
            )
        )

    if dataservice.get_value(PATH_HASRX):
        entities.append(
            AquariteBinarySensorEntity(
                dataservice,
                AquariteBinarySensorConfig(
                    "rx_pump_status",
                    "modules.rx.pump_status", BinarySensorDeviceClass.RUNNING,
                ),
                pool_id,
                pool_name,
            )
        )

    if any(
        dataservice.get_value(path)
        for path in (PATH_HASCD, PATH_HASCL, PATH_HASPH, PATH_HASRX)
    ):
        entities.append(
            AquariteBinarySensorTankEntity(
                dataservice, "acid_tank", pool_id, pool_name
            )
        )

    is_electrolysis = dataservice.get_value("hidro.is_electrolysis")
    low_key = "electrolysis_low" if is_electrolysis else "hydrolysis_low"
    entities.append(
        AquariteBinarySensorEntity(
            dataservice,
            AquariteBinarySensorConfig(
                low_key, "hidro.low", BinarySensorDeviceClass.PROBLEM
            ),
            pool_id,
            pool_name,
        )
    )

    async_add_entities(entities)


class AquariteBinarySensorEntity(AquariteEntity, BinarySensorEntity):
    """Representation of an Aquarite binary sensor."""

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        config: AquariteBinarySensorConfig,
        pool_id: str,
        pool_name: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = config.value_path
        self._attr_device_class = config.device_class
        self._attr_translation_key = config.translation_key
        self._attr_unique_id = self.build_unique_id(config.translation_key)
        if config.entity_category is not None:
            self._attr_entity_category = config.entity_category
        if not config.entity_registry_enabled_default:
            self._attr_entity_registry_enabled_default = False

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        value = self.coordinator.get_value(self._value_path)
        if value is None:
            return None
        return bool(int(value))


class AquariteBinarySensorTankEntity(AquariteEntity, BinarySensorEntity):
    """Tank level binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        translation_key: str,
        pool_id: str,
        pool_name: str,
    ) -> None:
        """Initialize the tank sensor."""
        super().__init__(dataservice, pool_id, pool_name)
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(translation_key)

    @property
    def is_on(self) -> bool:
        """Return true if any tank is low."""
        return any(
            self.coordinator.get_value(module) for module in TANK_MODULE_PATHS
        )
