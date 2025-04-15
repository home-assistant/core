"""Support for waterheater entities."""

from __future__ import annotations

import logging
from typing import Any

from thinqconnect import DeviceType
from thinqconnect.integration import ExtendedProperty

from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    STATE_ECO,
    STATE_HEAT_PUMP,
    STATE_OFF,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ThinqConfigEntry
from .coordinator import DeviceDataUpdateCoordinator
from .entity import ThinQEntity

DEVICE_TYPE_WH_MAP: dict[DeviceType, WaterHeaterEntityDescription] = {
    DeviceType.WATER_HEATER: WaterHeaterEntityDescription(
        key=ExtendedProperty.WATER_HEATER,
        name=None,
    ),
    DeviceType.SYSTEM_BOILER: WaterHeaterEntityDescription(
        key=ExtendedProperty.WATER_BOILER,
        name=None,
    ),
}

# Mapping between device and HA operation modes
DEVICE_OP_MODE_TO_HA = {
    "auto": STATE_ECO,
    "heat_pump": STATE_HEAT_PUMP,
    "turbo": STATE_PERFORMANCE,
    "vacation": STATE_OFF,
}
HA_STATE_TO_DEVICE_OP_MODE = {v: k for k, v in DEVICE_OP_MODE_TO_HA.items()}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an entry for water_heater platform."""
    entities: list[ThinQWaterHeaterEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        if (
            description := DEVICE_TYPE_WH_MAP.get(coordinator.api.device.device_type)
        ) is not None:
            if coordinator.api.device.device_type == DeviceType.WATER_HEATER:
                entities.append(
                    ThinQWaterHeaterEntity(
                        coordinator, description, ExtendedProperty.WATER_HEATER
                    )
                )
            elif coordinator.api.device.device_type == DeviceType.SYSTEM_BOILER:
                entities.append(
                    ThinQWaterBoilerEntity(
                        coordinator, description, ExtendedProperty.WATER_BOILER
                    )
                )
    if entities:
        async_add_entities(entities)


class ThinQWaterHeaterEntity(ThinQEntity, WaterHeaterEntity):
    """Represent a ThinQ water heater entity."""

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        entity_description: WaterHeaterEntityDescription,
        property_id: str,
    ) -> None:
        """Initialize a water_heater entity."""
        super().__init__(coordinator, entity_description, property_id)
        self._attr_supported_features = (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.OPERATION_MODE
        )
        self._attr_temperature_unit = (
            self._get_unit_of_measurement(self.data.unit) or UnitOfTemperature.CELSIUS
        )
        if modes := self.data.job_modes:
            self._attr_operation_list = [
                DEVICE_OP_MODE_TO_HA.get(mode, mode) for mode in modes
            ]
        else:
            self._attr_operation_list = [STATE_HEAT_PUMP]

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()
        self._attr_current_temperature = self.data.current_temp
        self._attr_target_temperature = self.data.target_temp

        if self.data.max is not None:
            self._attr_max_temp = self.data.max
        if self.data.min is not None:
            self._attr_min_temp = self.data.min
        if self.data.step is not None:
            self._attr_target_temperature_step = self.data.step

        self._attr_temperature_unit = (
            self._get_unit_of_measurement(self.data.unit) or UnitOfTemperature.CELSIUS
        )
        if self.data.is_on:
            self._attr_current_operation = (
                DEVICE_OP_MODE_TO_HA.get(job_mode, job_mode)
                if (job_mode := self.data.job_mode) is not None
                else STATE_HEAT_PUMP
            )
        else:
            self._attr_current_operation = STATE_OFF

        _LOGGER.debug(
            "[%s:%s] update status: c:%s, t:%s, op_mode:%s, op_list:%s, is_on:%s",
            self.coordinator.device_name,
            self.property_id,
            self.current_temperature,
            self.target_temperature,
            self.current_operation,
            self.operation_list,
            self.data.is_on,
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        _LOGGER.debug(
            "[%s:%s] async_set_temperature: %s",
            self.coordinator.device_name,
            self.property_id,
            kwargs,
        )
        if (operation_mode := kwargs.get(ATTR_OPERATION_MODE)) is not None:
            await self.async_set_operation_mode(str(operation_mode))
            if operation_mode == STATE_OFF:
                return

        if (
            temperature := kwargs.get(ATTR_TEMPERATURE)
        ) is not None and temperature != self.target_temperature:
            await self.async_call_api(
                self.coordinator.api.async_set_target_temperature(
                    self.property_id, temperature
                )
            )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        mode = HA_STATE_TO_DEVICE_OP_MODE.get(operation_mode, operation_mode)
        _LOGGER.debug(
            "[%s:%s] async_set_operation_mode: %s",
            self.coordinator.device_name,
            self.property_id,
            mode,
        )
        await self.async_call_api(
            self.coordinator.api.async_set_job_mode(self.property_id, mode)
        )


class ThinQWaterBoilerEntity(ThinQWaterHeaterEntity):
    """Represent a ThinQ water boiler entity."""

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        entity_description: WaterHeaterEntityDescription,
        property_id: str,
    ) -> None:
        """Initialize a water_heater entity."""
        super().__init__(coordinator, entity_description, property_id)
        self._attr_supported_features |= WaterHeaterEntityFeature.ON_OFF

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        _LOGGER.debug(
            "[%s:%s] async_turn_on", self.coordinator.device_name, self.property_id
        )
        await self.async_call_api(self.coordinator.api.async_turn_on(self.property_id))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        _LOGGER.debug(
            "[%s:%s] async_turn_off", self.coordinator.device_name, self.property_id
        )
        await self.async_call_api(self.coordinator.api.async_turn_off(self.property_id))
