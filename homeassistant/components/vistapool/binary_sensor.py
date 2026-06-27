"""Vistapool Binary Sensor entities."""

from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VistapoolConfigEntry
from .const import (
    PATH_HASCD,
    PATH_HASCL,
    PATH_HASHIDRO,
    PATH_HASIO,
    PATH_HASPH,
    PATH_HASRX,
)
from .coordinator import VistapoolDataUpdateCoordinator
from .entity import VistapoolEntity

PARALLEL_UPDATES = 0

TANK_MODULE_PATHS = (
    "modules.ph.tank",
    "modules.rx.tank",
    "modules.cl.tank",
    "modules.cd.tank",
)


@dataclass(frozen=True, kw_only=True)
class VistapoolBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Vistapool binary sensor entity."""

    value_path: str
    exists_path: str | tuple[str, ...] | None = None


BINARY_SENSOR_DESCRIPTIONS: tuple[VistapoolBinarySensorEntityDescription, ...] = (
    VistapoolBinarySensorEntityDescription(
        key="filtration",
        translation_key="filtration",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_path="filtration.status",
    ),
    VistapoolBinarySensorEntityDescription(
        key="backwash",
        translation_key="backwash",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_path="backwash.status",
    ),
    VistapoolBinarySensorEntityDescription(
        key="heating",
        translation_key="heating",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_path="relays.filtration.heating.status",
    ),
    VistapoolBinarySensorEntityDescription(
        key="hidro_flow",
        translation_key="hidro_flow",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_path="hidro.fl1",
        exists_path=PATH_HASHIDRO,
    ),
    VistapoolBinarySensorEntityDescription(
        key="hidro_cover_reduction",
        translation_key="hidro_cover_reduction",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_path="hidro.cover",
        exists_path=PATH_HASHIDRO,
    ),
    VistapoolBinarySensorEntityDescription(
        key="hidro_fl2",
        translation_key="hidro_fl2",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_path="hidro.fl2",
        exists_path=(PATH_HASHIDRO, PATH_HASCL),
    ),
    VistapoolBinarySensorEntityDescription(
        key="chlorine_pump",
        translation_key="chlorine_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_path="modules.cl.pump_status",
        exists_path=PATH_HASCL,
    ),
    VistapoolBinarySensorEntityDescription(
        key="redox_pump",
        translation_key="redox_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_path="modules.rx.pump_status",
        exists_path=PATH_HASRX,
    ),
    VistapoolBinarySensorEntityDescription(
        key="ph_pump_alarm",
        translation_key="ph_pump_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_path="modules.ph.al3",
        exists_path=PATH_HASPH,
    ),
    VistapoolBinarySensorEntityDescription(
        key="ph_acid_pump",
        translation_key="ph_acid_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_path="modules.ph.pump_high_on",
        exists_path=PATH_HASPH,
    ),
    VistapoolBinarySensorEntityDescription(
        key="ph_base_pump",
        translation_key="ph_base_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_path="modules.ph.pump_low_on",
        exists_path=PATH_HASPH,
    ),
    VistapoolBinarySensorEntityDescription(
        key="conductivity_module",
        translation_key="conductivity_module",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=PATH_HASCD,
    ),
    VistapoolBinarySensorEntityDescription(
        key="chlorine_module",
        translation_key="chlorine_module",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=PATH_HASCL,
    ),
    VistapoolBinarySensorEntityDescription(
        key="redox_module",
        translation_key="redox_module",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=PATH_HASRX,
    ),
    VistapoolBinarySensorEntityDescription(
        key="ph_module",
        translation_key="ph_module",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=PATH_HASPH,
    ),
    VistapoolBinarySensorEntityDescription(
        key="io_module",
        translation_key="io_module",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=PATH_HASIO,
    ),
    VistapoolBinarySensorEntityDescription(
        key="hidro_module",
        translation_key="hidro_module",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=PATH_HASHIDRO,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VistapoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vistapool binary sensors for every pool on the account."""
    entities: list[BinarySensorEntity] = []

    for coordinator in entry.runtime_data.coordinators.values():
        for description in BINARY_SENSOR_DESCRIPTIONS:
            if description.exists_path is not None:
                required = (
                    (description.exists_path,)
                    if isinstance(description.exists_path, str)
                    else description.exists_path
                )
                if not all(coordinator.get_value(path) for path in required):
                    continue
            entities.append(VistapoolBinarySensor(coordinator, description))

        if coordinator.get_value(PATH_HASHIDRO):
            is_electrolysis = coordinator.get_value("hidro.is_electrolysis")
            entities.append(
                VistapoolBinarySensor(
                    coordinator,
                    VistapoolBinarySensorEntityDescription(
                        key="electrolysis_low" if is_electrolysis else "hydrolysis_low",
                        translation_key=(
                            "electrolysis_low" if is_electrolysis else "hydrolysis_low"
                        ),
                        device_class=BinarySensorDeviceClass.PROBLEM,
                        value_path="hidro.low",
                    ),
                )
            )

        if any(
            coordinator.get_value(path)
            for path in (PATH_HASCD, PATH_HASCL, PATH_HASPH, PATH_HASRX)
        ):
            entities.append(VistapoolDosingTankBinarySensor(coordinator))

    async_add_entities(entities)


class VistapoolBinarySensor(VistapoolEntity, BinarySensorEntity):
    """Generic Vistapool binary sensor driven by an entity description."""

    entity_description: VistapoolBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: VistapoolDataUpdateCoordinator,
        description: VistapoolBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = self.build_unique_id(description.key)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        value = self.coordinator.get_value(self.entity_description.value_path)
        if value is None:
            return None
        return value in (True, "1")


class VistapoolDosingTankBinarySensor(VistapoolEntity, BinarySensorEntity):
    """Dosing-tank low-level sensor: on if any installed dosing module reports low."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "dosing_tank"

    def __init__(self, coordinator: VistapoolDataUpdateCoordinator) -> None:
        """Initialize the dosing-tank binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = self.build_unique_id("dosing_tank")

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if any tank is low, or None if no tank data is available."""
        values: list[Any] = []
        for path in TANK_MODULE_PATHS:
            value = self.coordinator.get_value(path)
            if value is not None:
                values.append(value)
        if not values:
            return None
        return any(value in (True, "1") for value in values)
