"""The Nibe Heat Pump sensors."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from nibe.coil import Coil
from nibe.exceptions import CoilNotFoundException
from nibe.heatpump import Series

from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    STATE_HEAT_PUMP,
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, LOGGER, Coordinator
from .const import VALUES_PRIORITY_HOT_WATER


@dataclass
class WaterHeaterDescriptionMixin:
    """Mixin for required fields."""

    hot_water_load_address: int
    hot_water_comfort_mode_address: int
    start_temperature_address: dict[str, int]
    stop_temperature_address: dict[str, int]
    prio_address: int
    active_accessory_address: int | None


@dataclass
class WaterHeaterDescription(
    WaterHeaterEntityEntityDescription, WaterHeaterDescriptionMixin
):
    """Base description."""


WATER_HEATERS_F = (
    WaterHeaterDescription(
        key="hw1",
        name="Hot Water",
        hot_water_load_address=40014,
        hot_water_comfort_mode_address=47041,
        start_temperature_address={
            "ECONOMY": 47045,
            "NORMAL": 47044,
            "LUXURY": 47043,
        },
        stop_temperature_address={
            "ECONOMY": 47049,
            "NORMAL": 47048,
            "LUXURY": 47047,
        },
        prio_address=43086,
        active_accessory_address=None,
    ),
)

WATER_HEATERS_S = (
    WaterHeaterDescription(
        key="hw1",
        name="Hot Water",
        hot_water_load_address=30010,
        hot_water_comfort_mode_address=31039,
        start_temperature_address={
            "LOW": 40061,
            "NORMAL": 40060,
            "HIGH": 40059,
        },
        stop_temperature_address={
            "LOW": 40065,
            "NORMAL": 40064,
            "HIGH": 40063,
        },
        prio_address=31029,
        active_accessory_address=None,
    ),
)

WATER_HEATERS = {
    Series.F: WATER_HEATERS_F,
    Series.S: WATER_HEATERS_S,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator: Coordinator = hass.data[DOMAIN][config_entry.entry_id]

    def water_heaters():
        for entity_description in WATER_HEATERS.get(coordinator.series, ()):
            try:
                yield WaterHeater(coordinator, entity_description)
            except CoilNotFoundException as exception:
                LOGGER.debug("Skipping water heater: %r", exception)

    async_add_entities(water_heaters())


class WaterHeaterEntityFixed(WaterHeaterEntity):
    """Base class to disentangle the configuration of operation mode from the state."""

    _attr_operation_mode: str | None

    @property
    def operation_mode(self) -> str | None:
        """Return the operation modes currently configured."""
        if hasattr(self, "_attr_operation_mode"):
            return self._attr_operation_mode
        return self.current_operation

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes."""
        data = {}
        supported_features = self.supported_features or 0
        if supported_features & WaterHeaterEntityFeature.OPERATION_MODE:
            data[ATTR_OPERATION_MODE] = self._attr_operation_mode
        return data


class WaterHeater(CoordinatorEntity[Coordinator], WaterHeaterEntityFixed):
    """Sensor entity."""

    _attr_entity_category = None
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_supported_features = WaterHeaterEntityFeature.OPERATION_MODE
    _attr_max_temp = 35.0
    _attr_min_temp = 5.0

    entity_description: WaterHeaterDescription

    def __init__(self, coordinator: Coordinator, desc: WaterHeaterDescription) -> None:
        """Initialize entity."""

        super().__init__(
            coordinator,
            {
                desc.hot_water_load_address,
                desc.hot_water_comfort_mode_address,
                *set(desc.start_temperature_address.values()),
                *set(desc.stop_temperature_address.values()),
                desc.prio_address,
                desc.active_accessory_address,
            },
        )
        self.entity_description = desc
        self._attr_entity_registry_enabled_default = (
            desc.active_accessory_address is None
        )
        self._attr_available = False
        self._attr_name = desc.name
        self._attr_unique_id = f"{coordinator.unique_id}-{desc.key}"
        self._attr_device_info = coordinator.device_info

        self._attr_current_operation = None
        self._attr_operation_mode = None
        self._attr_target_temperature_high = None
        self._attr_target_temperature_low = None
        self._attr_operation_list: list[str] | None = None

        def _get(address: int) -> Coil:
            return coordinator.heatpump.get_coil_by_address(address)

        def _map(data: dict[str, int]) -> dict[str, Coil]:
            return {key: _get(address) for key, address in data.items()}

        self._coil_current = _get(desc.hot_water_load_address)
        self._coil_start_temperature = _map(desc.start_temperature_address)
        self._coil_stop_temperature = _map(desc.stop_temperature_address)
        self._coil_prio = _get(desc.prio_address)
        self._coil_active_accessory: Coil | None = None
        if address := desc.active_accessory_address:
            self._coil_active_accessory = _get(address)

        self._coil_hot_water_comfort_mode = _get(desc.hot_water_comfort_mode_address)
        if mappings := self._coil_hot_water_comfort_mode.mappings:
            self._attr_operation_list = list(mappings.values())

        self._attr_temperature_unit = self._coil_current.unit

    def _handle_coordinator_update(self) -> None:
        if not self.coordinator.data:
            return

        def _get_float(coil: Coil | None) -> float | None:
            if coil is None:
                return None
            return self.coordinator.get_coil_float(coil)

        def _get_value(coil: Coil | None) -> int | str | float | None:
            if coil is None:
                return None
            return self.coordinator.get_coil_value(coil)

        self._attr_current_temperature = _get_float(self._coil_current)

        if (mode := _get_value(self._coil_hot_water_comfort_mode)) and isinstance(
            mode, str
        ):
            self._attr_operation_mode = mode
            self._attr_target_temperature_low = _get_float(
                self._coil_start_temperature.get(mode)
            )
            self._attr_target_temperature_high = _get_float(
                self._coil_stop_temperature.get(mode)
            )
        else:
            self._attr_operation_mode = None
            self._attr_target_temperature_low = None
            self._attr_target_temperature_high = None

        if prio := _get_value(self._coil_prio):
            if prio in VALUES_PRIORITY_HOT_WATER:
                self._attr_current_operation = STATE_HEAT_PUMP
            else:
                self._attr_current_operation = STATE_OFF
        else:
            self._attr_current_operation = None

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        if not self._coil_active_accessory:
            return True

        if active_accessory := self.coordinator.get_coil_value(
            self._coil_active_accessory
        ):
            return active_accessory == "ON"

        return False

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        await self.coordinator.async_write_coil(
            self._coil_hot_water_comfort_mode, operation_mode
        )
