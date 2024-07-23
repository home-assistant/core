"""The Nibe Heat Pump sensors."""

from __future__ import annotations

from datetime import date

from nibe.coil import Coil
from nibe.coil_groups import WATER_HEATER_COILGROUPS, WaterHeaterCoilGroup
from nibe.exceptions import CoilNotFoundException

from homeassistant.components.water_heater import (
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    LOGGER,
    VALUES_TEMPORARY_LUX_INACTIVE,
    VALUES_TEMPORARY_LUX_ONE_TIME_INCREASE,
)
from .coordinator import Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator: Coordinator = hass.data[DOMAIN][config_entry.entry_id]

    def water_heaters():
        for key, group in WATER_HEATER_COILGROUPS.get(coordinator.series, ()).items():
            try:
                yield WaterHeater(coordinator, key, group)
            except CoilNotFoundException as exception:
                LOGGER.debug("Skipping water heater: %r", exception)

    async_add_entities(water_heaters())


class WaterHeater(CoordinatorEntity[Coordinator], WaterHeaterEntity):
    """Sensor entity."""

    _attr_entity_category = None
    _attr_has_entity_name = True
    _attr_supported_features = WaterHeaterEntityFeature.OPERATION_MODE
    _attr_max_temp = 35.0
    _attr_min_temp = 5.0

    def __init__(
        self,
        coordinator: Coordinator,
        key: str,
        desc: WaterHeaterCoilGroup,
    ) -> None:
        """Initialize entity."""

        super().__init__(
            coordinator,
            {
                desc.hot_water_load,
                desc.hot_water_comfort_mode,
                *set(desc.start_temperature.values()),
                *set(desc.stop_temperature.values()),
                desc.active_accessory,
                desc.temporary_lux,
            },
        )
        self._attr_entity_registry_enabled_default = desc.active_accessory is None
        self._attr_available = False
        self._attr_name = desc.name
        self._attr_unique_id = f"{coordinator.unique_id}-{key}"
        self._attr_device_info = coordinator.device_info

        self._attr_current_operation = None
        self._attr_target_temperature_high = None
        self._attr_target_temperature_low = None
        self._attr_operation_list = []
        self._operation_mode_to_lux: dict[str, str] = {}

        def _get(address: int) -> Coil:
            return coordinator.heatpump.get_coil_by_address(address)

        def _map(data: dict[str, int]) -> dict[str, Coil]:
            return {key: _get(address) for key, address in data.items()}

        self._coil_current = _get(desc.hot_water_load)
        self._coil_start_temperature = _map(desc.start_temperature)
        self._coil_stop_temperature = _map(desc.stop_temperature)
        self._coil_temporary_lux: Coil | None = None
        if desc.temporary_lux:
            self._coil_temporary_lux = _get(desc.temporary_lux)
        self._coil_active_accessory: Coil | None = None
        if address := desc.active_accessory:
            self._coil_active_accessory = _get(address)

        self._coil_hot_water_comfort_mode = _get(desc.hot_water_comfort_mode)

        def _add_lux_mode(temporary_lux: str, operation_mode: str) -> None:
            assert self._attr_operation_list is not None
            if (
                not self._coil_temporary_lux
                or not self._coil_temporary_lux.reverse_mappings
            ):
                return

            if temporary_lux not in self._coil_temporary_lux.reverse_mappings:
                return

            self._attr_operation_list.append(operation_mode)
            self._operation_mode_to_lux[operation_mode] = temporary_lux

        _add_lux_mode(VALUES_TEMPORARY_LUX_ONE_TIME_INCREASE, STATE_HIGH_DEMAND)
        _add_lux_mode(VALUES_TEMPORARY_LUX_INACTIVE, STATE_HEAT_PUMP)

        self._attr_temperature_unit = self._coil_current.unit

    @callback
    def _handle_coordinator_update(self) -> None:
        if not self.coordinator.data:
            return

        def _get_float(coil: Coil | None) -> float | None:
            if coil is None:
                return None
            return self.coordinator.get_coil_float(coil)

        def _get_value(coil: Coil | None) -> int | str | float | date | None:
            if coil is None:
                return None
            return self.coordinator.get_coil_value(coil)

        self._attr_current_temperature = _get_float(self._coil_current)

        if (mode := _get_value(self._coil_hot_water_comfort_mode)) and isinstance(
            mode, str
        ):
            self._attr_target_temperature_low = _get_float(
                self._coil_start_temperature.get(mode)
            )
            self._attr_target_temperature_high = _get_float(
                self._coil_stop_temperature.get(mode)
            )
        else:
            self._attr_target_temperature_low = None
            self._attr_target_temperature_high = None

        if (
            _get_value(self._coil_temporary_lux)
            == VALUES_TEMPORARY_LUX_ONE_TIME_INCREASE
        ):
            self._attr_current_operation = STATE_HIGH_DEMAND
        else:
            self._attr_current_operation = STATE_HEAT_PUMP

        super()._handle_coordinator_update()

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
        if not self._coil_temporary_lux:
            raise HomeAssistantError("Not supported")

        lux = self._operation_mode_to_lux.get(operation_mode)
        if not lux:
            raise ValueError(f"Unsupported operation mode {operation_mode}")

        await self.coordinator.async_write_coil(self._coil_temporary_lux, lux)
