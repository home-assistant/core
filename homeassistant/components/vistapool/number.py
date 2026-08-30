"""Vistapool Number entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aioaquarite import AquariteError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VistapoolConfigEntry
from .const import DOMAIN, PATH_HASHIDRO, PATH_HASPH, PATH_HASRX, SIGNAL_NEW_POOL
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
    max_value_fn: Callable[[VistapoolDataUpdateCoordinator], float] | None = None


def _max_electrolysis(coordinator: VistapoolDataUpdateCoordinator) -> float:
    """Read the cell's hardware max, falling back to a safe default."""
    raw = coordinator.get_value("hidro.maxAllowedValue")
    if raw is None:
        return 50.0
    try:
        return float(raw) / 10
    except TypeError, ValueError:
        return 50.0


NUMBER_DESCRIPTIONS: tuple[VistapoolNumberEntityDescription, ...] = (
    VistapoolNumberEntityDescription(
        key="redox_setpoint",
        translation_key="redox_setpoint",
        entity_category=EntityCategory.CONFIG,
        native_min_value=500,
        native_max_value=800,
        native_step=1,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
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
    *(
        VistapoolNumberEntityDescription(
            key=key,
            translation_key=key,
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
            native_min_value=_TEMP_MIN,
            native_max_value=_TEMP_MAX,
            native_step=1,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            value_path=value_path,
            exists_path=exists_path,
        )
        for key, value_path, exists_path in (
            (
                "heating_minimum_temperature",
                "filtration.heating.temp",
                "filtration.hasHeat",
            ),
            (
                "heating_maximum_temperature",
                "filtration.heating.tempHi",
                "filtration.hasHeat",
            ),
            (
                "smart_minimum_temperature",
                "filtration.smart.tempMin",
                "filtration.hasSmart",
            ),
            (
                "smart_maximum_temperature",
                "filtration.smart.tempHigh",
                "filtration.hasSmart",
            ),
        )
    ),
)


def _build_number_entities(
    coordinator: VistapoolDataUpdateCoordinator,
) -> list[NumberEntity]:
    """Build the number entities for a single pool."""
    entities: list[NumberEntity] = []
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
        key = (
            "hydrolysis_setpoint"
            if coordinator.get_value("hidro.is_electrolysis") is False
            else "electrolysis_setpoint"
        )
        entities.append(
            VistapoolNumber(
                coordinator,
                VistapoolNumberEntityDescription(
                    key=key,
                    translation_key=key,
                    entity_category=EntityCategory.CONFIG,
                    native_min_value=0,
                    native_max_value=50.0,
                    native_step=0.1,
                    native_unit_of_measurement="g/h",
                    value_path="hidro.level",
                    scale=10,
                    max_value_fn=_max_electrolysis,
                ),
            )
        )
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VistapoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vistapool number entities for every pool on the account."""
    entities: list[NumberEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        entities.extend(_build_number_entities(coordinator))
    async_add_entities(entities)

    @callback
    def _async_add_pool(coordinator: VistapoolDataUpdateCoordinator) -> None:
        async_add_entities(_build_number_entities(coordinator))

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_NEW_POOL}_{entry.entry_id}", _async_add_pool
        )
    )


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
    @override
    def native_max_value(self) -> float:
        """Return the max value, recomputed from coordinator data when applicable."""
        if (fn := self.entity_description.max_value_fn) is not None:
            return fn(self.coordinator)
        return super().native_max_value

    @property
    @override
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

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Send the de-scaled value to the controller."""
        raw = round(value * self.entity_description.scale)
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
        self.coordinator.apply_optimistic(self.entity_description.value_path, raw)
