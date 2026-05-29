"""Vistapool Number entities."""

from dataclasses import dataclass

from aioaquarite import AquariteError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VistapoolConfigEntry
from .const import DOMAIN, PATH_HASHIDRO, PATH_HASPH, PATH_HASRX
from .coordinator import VistapoolDataUpdateCoordinator
from .entity import VistapoolEntity

PARALLEL_UPDATES = 1

_TEMP_MIN = 5.0
_TEMP_MAX = 40.0


@dataclass(frozen=True, kw_only=True)
class VistapoolNumberEntityDescription(NumberEntityDescription):
    """Describes a Vistapool number entity."""

    value_path: str
    scale: int = 1
    exists_path: str | tuple[str, ...] | None = None


NUMBER_DESCRIPTIONS: tuple[VistapoolNumberEntityDescription, ...] = (
    VistapoolNumberEntityDescription(
        key="redox_setpoint",
        translation_key="redox_setpoint",
        entity_category=EntityCategory.CONFIG,
        native_min_value=500,
        native_max_value=800,
        native_step=1,
        native_unit_of_measurement="mV",
        value_path="modules.rx.status.value",
        exists_path=PATH_HASRX,
    ),
    VistapoolNumberEntityDescription(
        key="ph_minimum",
        translation_key="ph_minimum",
        device_class=NumberDeviceClass.PH,
        entity_category=EntityCategory.CONFIG,
        native_min_value=6,
        native_max_value=8,
        native_step=0.01,
        value_path="modules.ph.status.low_value",
        scale=100,
        exists_path=PATH_HASPH,
    ),
    VistapoolNumberEntityDescription(
        key="ph_maximum",
        translation_key="ph_maximum",
        device_class=NumberDeviceClass.PH,
        entity_category=EntityCategory.CONFIG,
        native_min_value=6,
        native_max_value=8,
        native_step=0.01,
        value_path="modules.ph.status.high_value",
        scale=100,
        exists_path=PATH_HASPH,
    ),
    VistapoolNumberEntityDescription(
        key="intel_temperature",
        translation_key="intel_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_min_value=_TEMP_MIN,
        native_max_value=_TEMP_MAX,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_path="filtration.intel.temp",
    ),
)


def _max_electrolysis(coordinator: VistapoolDataUpdateCoordinator) -> float:
    """Read the cell's hardware max, falling back to a safe default."""
    raw = coordinator.get_value("hidro.maxAllowedValue")
    if raw is None:
        return 50.0
    try:
        return float(raw) / 10
    except TypeError, ValueError:
        return 50.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VistapoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vistapool number entities for every pool on the account."""
    entities: list[NumberEntity] = []

    for coordinator in entry.runtime_data.coordinators.values():
        for description in NUMBER_DESCRIPTIONS:
            if description.exists_path is not None:
                required = (
                    (description.exists_path,)
                    if isinstance(description.exists_path, str)
                    else description.exists_path
                )
                if not all(coordinator.get_value(path) for path in required):
                    continue
            entities.append(VistapoolNumber(coordinator, description))

        if coordinator.get_value(PATH_HASHIDRO):
            entities.append(
                VistapoolNumber(
                    coordinator,
                    VistapoolNumberEntityDescription(
                        key="electrolysis_setpoint",
                        translation_key="electrolysis_setpoint",
                        entity_category=EntityCategory.CONFIG,
                        native_min_value=0,
                        native_max_value=_max_electrolysis(coordinator),
                        native_step=0.1,
                        native_unit_of_measurement="g/h",
                        value_path="hidro.level",
                        scale=10,
                    ),
                )
            )

        if coordinator.get_value("filtration.hasHeat"):
            entities.extend(
                VistapoolNumber(coordinator, description)
                for description in (
                    VistapoolNumberEntityDescription(
                        key="heating_minimum_temperature",
                        translation_key="heating_minimum_temperature",
                        device_class=NumberDeviceClass.TEMPERATURE,
                        entity_category=EntityCategory.CONFIG,
                        native_min_value=_TEMP_MIN,
                        native_max_value=_TEMP_MAX,
                        native_step=1,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        value_path="filtration.heating.temp",
                    ),
                    VistapoolNumberEntityDescription(
                        key="heating_maximum_temperature",
                        translation_key="heating_maximum_temperature",
                        device_class=NumberDeviceClass.TEMPERATURE,
                        entity_category=EntityCategory.CONFIG,
                        native_min_value=_TEMP_MIN,
                        native_max_value=_TEMP_MAX,
                        native_step=1,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        value_path="filtration.heating.tempHi",
                    ),
                )
            )

        if coordinator.get_value("filtration.hasSmart"):
            entities.extend(
                VistapoolNumber(coordinator, description)
                for description in (
                    VistapoolNumberEntityDescription(
                        key="smart_minimum_temperature",
                        translation_key="smart_minimum_temperature",
                        device_class=NumberDeviceClass.TEMPERATURE,
                        entity_category=EntityCategory.CONFIG,
                        native_min_value=_TEMP_MIN,
                        native_max_value=_TEMP_MAX,
                        native_step=1,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        value_path="filtration.smart.tempMin",
                    ),
                    VistapoolNumberEntityDescription(
                        key="smart_maximum_temperature",
                        translation_key="smart_maximum_temperature",
                        device_class=NumberDeviceClass.TEMPERATURE,
                        entity_category=EntityCategory.CONFIG,
                        native_min_value=_TEMP_MIN,
                        native_max_value=_TEMP_MAX,
                        native_step=1,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        value_path="filtration.smart.tempHigh",
                    ),
                )
            )

    async_add_entities(entities)


class VistapoolNumber(VistapoolEntity, NumberEntity):
    """Generic Vistapool number driven by an entity description."""

    entity_description: VistapoolNumberEntityDescription

    def __init__(
        self,
        coordinator: VistapoolDataUpdateCoordinator,
        description: VistapoolNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = self.build_unique_id(description.key)

    @property
    def native_value(self) -> float | None:
        """Return the scaled current value."""
        raw = self.coordinator.get_value(self.entity_description.value_path)
        if raw is None:
            return None
        try:
            value = float(raw)
        except TypeError, ValueError:
            return None
        return value / self.entity_description.scale

    async def async_set_native_value(self, value: float) -> None:
        """Send the de-scaled value to the controller."""
        scale = self.entity_description.scale
        raw: int | float = round(value * scale) if scale != 1 else value
        try:
            await self.coordinator.api.set_value(
                self.coordinator.pool_id,
                self.entity_description.value_path,
                raw,
            )
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={"entity": self.entity_id},
            ) from err
