"""Vistapool Binary Sensor entities."""

from dataclasses import dataclass

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

PARALLEL_UPDATES = 1

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
        key="filtration_status",
        translation_key="filtration_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_path="filtration.status",
    ),
    VistapoolBinarySensorEntityDescription(
        key="backwash_status",
        translation_key="backwash_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_path="backwash.status",
    ),
    VistapoolBinarySensorEntityDescription(
        key="heating_status",
        translation_key="heating_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_path="relays.filtration.heating.status",
    ),
    VistapoolBinarySensorEntityDescription(
        key="hidro_flow_status",
        translation_key="hidro_flow_status",
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
        key="hidro_fl2_status",
        translation_key="hidro_fl2_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_path="hidro.fl2",
        exists_path=(PATH_HASHIDRO, PATH_HASCL),
    ),
    VistapoolBinarySensorEntityDescription(
        key="cl_pump_status",
        translation_key="cl_pump_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_path="modules.cl.pump_status",
        exists_path=PATH_HASCL,
    ),
    VistapoolBinarySensorEntityDescription(
        key="rx_pump_status",
        translation_key="rx_pump_status",
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
        key="cd_module_installed",
        translation_key="cd_module_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=PATH_HASCD,
    ),
    VistapoolBinarySensorEntityDescription(
        key="cl_module_installed",
        translation_key="cl_module_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=PATH_HASCL,
    ),
    VistapoolBinarySensorEntityDescription(
        key="rx_module_installed",
        translation_key="rx_module_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=PATH_HASRX,
    ),
    VistapoolBinarySensorEntityDescription(
        key="ph_module_installed",
        translation_key="ph_module_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=PATH_HASPH,
    ),
    VistapoolBinarySensorEntityDescription(
        key="io_module_installed",
        translation_key="io_module_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=PATH_HASIO,
    ),
    VistapoolBinarySensorEntityDescription(
        key="hidro_module_installed",
        translation_key="hidro_module_installed",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
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
            entities.append(VistapoolAcidTankBinarySensor(coordinator))

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
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        value = self.coordinator.get_value(self.entity_description.value_path)
        if value is None:
            return None
        return bool(value)


class VistapoolAcidTankBinarySensor(VistapoolEntity, BinarySensorEntity):
    """Acid-tank low-level sensor: on if any installed dosing module reports low."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "acid_tank"

    def __init__(self, coordinator: VistapoolDataUpdateCoordinator) -> None:
        """Initialize the acid-tank binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = self.build_unique_id("acid_tank")

    @property
    def is_on(self) -> bool | None:
        """Return true if any tank is low, or None if no tank data is available."""
        values = [
            value
            for path in TANK_MODULE_PATHS
            if (value := self.coordinator.get_value(path)) is not None
        ]
        if not values:
            return None
        return any(bool(value) for value in values)
