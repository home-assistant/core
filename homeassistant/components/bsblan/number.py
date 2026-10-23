"""Support for BSB-LAN setpoint numbers."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.climate import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BSBLanConfigEntry, BSBLanData
from .const import DEFAULT_HOT_WATER_MIN_TEMP
from .entity import BSBLanCircuitEntity, BSBLanWaterHeaterDeviceEntity
from .helpers import circuit_temperature_bounds, first_temperature

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class BSBLanSetpointNumberEntityDescription(NumberEntityDescription):
    """Describes a BSB-LAN setpoint number entity."""

    reduced: bool


COMFORT_TEMPERATURE = BSBLanSetpointNumberEntityDescription(
    key="comfort_temperature",
    translation_key="comfort_temperature",
    device_class=NumberDeviceClass.TEMPERATURE,
    entity_category=EntityCategory.CONFIG,
    native_step=0.5,
    reduced=False,
)
NOMINAL_TEMPERATURE = BSBLanSetpointNumberEntityDescription(
    key="nominal_temperature",
    translation_key="nominal_temperature",
    device_class=NumberDeviceClass.TEMPERATURE,
    entity_category=EntityCategory.CONFIG,
    native_step=0.5,
    reduced=False,
)
REDUCED_TEMPERATURE = BSBLanSetpointNumberEntityDescription(
    key="reduced_temperature",
    translation_key="reduced_temperature",
    device_class=NumberDeviceClass.TEMPERATURE,
    entity_category=EntityCategory.CONFIG,
    native_step=0.5,
    reduced=True,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BSBLanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BSB-LAN setpoint numbers based on a config entry."""
    data = entry.runtime_data
    entities: list[NumberEntity] = []
    for circuit in data.available_circuits:
        state = data.fast_coordinator.data.states[circuit]
        if first_temperature(state.target_temperature) is not None:
            entities.append(
                BSBLanCircuitSetpointNumber(data, circuit, COMFORT_TEMPERATURE)
            )
        if (static := data.static.get(circuit)) is not None and first_temperature(
            static.temp_reduced_setpoint
        ) is not None:
            entities.append(
                BSBLanCircuitSetpointNumber(data, circuit, REDUCED_TEMPERATURE)
            )
    if (dhw := data.fast_coordinator.data.dhw) is not None and (
        first_temperature(dhw.nominal_setpoint) is not None
    ):
        entities.extend(
            BSBLanHotWaterSetpointNumber(data, description)
            for description in (NOMINAL_TEMPERATURE, REDUCED_TEMPERATURE)
        )
    async_add_entities(entities)


class BSBLanCircuitSetpointNumber(BSBLanCircuitEntity, NumberEntity):
    """Defines a BSB-LAN heating circuit setpoint."""

    entity_description: BSBLanSetpointNumberEntityDescription

    def __init__(
        self,
        data: BSBLanData,
        circuit: int,
        description: BSBLanSetpointNumberEntityDescription,
    ) -> None:
        """Initialize BSB-LAN heating circuit setpoint."""
        super().__init__(data.fast_coordinator, data.slow_coordinator, data, circuit)
        self.entity_description = description
        self._attr_unique_id = (
            f"{format_mac(data.device.MAC)}-circuit-{circuit}-{description.key}"
        )
        self._attr_native_unit_of_measurement = (
            data.fast_coordinator.client.get_temperature_unit
        )
        min_temp, max_temp = circuit_temperature_bounds(data.static.get(circuit))
        self._attr_native_min_value = (
            min_temp if min_temp is not None else DEFAULT_MIN_TEMP
        )
        self._attr_native_max_value = (
            max_temp if max_temp is not None else DEFAULT_MAX_TEMP
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the setpoint."""
        if self.entity_description.reduced:
            return self._reduced_setpoint
        return self._comfort_setpoint

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the setpoint."""
        reduced = self.entity_description.reduced
        self._validate_setpoint(value, reduced=reduced)
        await self._async_set_setpoint(value, reduced=reduced)


class BSBLanHotWaterSetpointNumber(BSBLanWaterHeaterDeviceEntity, NumberEntity):
    """Defines a BSB-LAN hot water setpoint."""

    entity_description: BSBLanSetpointNumberEntityDescription
    _attr_native_min_value = DEFAULT_HOT_WATER_MIN_TEMP

    def __init__(
        self,
        data: BSBLanData,
        description: BSBLanSetpointNumberEntityDescription,
    ) -> None:
        """Initialize BSB-LAN hot water setpoint."""
        super().__init__(data.fast_coordinator, data.slow_coordinator, data)
        self.entity_description = description
        self._attr_unique_id = (
            f"{format_mac(data.device.MAC)}-water-heater-{description.key}"
        )
        self._attr_native_unit_of_measurement = (
            data.fast_coordinator.client.get_temperature_unit
        )

    @property
    @override
    def native_max_value(self) -> float:
        """Return the highest setpoint."""
        return self._setpoint_max

    @property
    @override
    def native_value(self) -> float | None:
        """Return the setpoint."""
        if self.entity_description.reduced:
            return self._reduced_setpoint
        return self._nominal_setpoint

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the setpoint."""
        reduced = self.entity_description.reduced
        self._validate_setpoint(value, reduced=reduced)
        await self._async_set_setpoint(value, reduced=reduced)
