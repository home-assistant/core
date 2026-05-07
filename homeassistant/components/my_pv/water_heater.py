# pylint: disable=duplicate-code
"""Creates Water Heater entities for the my-PV Home Assistant integration."""

import logging
from typing import Any

from homeassistant.components.water_heater import (
    STATE_ELECTRIC,
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MyPVCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV water heater."""
    coordinator: MyPVCoordinator = config_entry.runtime_data
    entities = []

    if (
        coordinator.get_setup_configuration("devmode")
        and coordinator.get_data_configuration("temp1")
        and (
            target_temperature_config := coordinator.get_setup_configuration(
                "ww1target"
            )
        )
    ):
        entity_description = MyPVWaterHeaterEntityDescription(
            key="boiler",
            temperature_unit=target_temperature_config["unit"],
            current_temperature_key="temp1",
            target_temperature_key="ww1target",
            target_temperature_step=target_temperature_config["step"],
            max_temp=target_temperature_config["max"],
            min_temp=target_temperature_config["min"],
        )
        entities.append(
            MyPVWaterHeater(
                coordinator,
                entity_description,
                config_entry.entry_id,
            )
        )

    async_add_entities(entities)


class MyPVWaterHeaterEntityDescription(
    WaterHeaterEntityDescription, frozen_or_thawed=True
):
    """A class that describes my-PV water heater entities."""

    current_temperature_key: str
    target_temperature_key: str
    target_temperature_step: float
    max_temp: float
    min_temp: float
    temperature_unit: str


class MyPVWaterHeater(CoordinatorEntity, WaterHeaterEntity):
    """Base my-PV WaterHeater."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_available = False
    _attr_supported_features = (
        WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    coordinator: MyPVCoordinator
    entity_description: MyPVWaterHeaterEntityDescription

    def __init__(
        self,
        coordinator: MyPVCoordinator,
        entity_description: MyPVWaterHeaterEntityDescription,
        config_entry_id: str,
    ) -> None:
        """Initialize the water_heater."""
        super().__init__(coordinator, entity_description.key)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{config_entry_id}-{entity_description.key}"

        self.entity_description = entity_description

        self._attr_target_temperature_step = entity_description.target_temperature_step
        self._attr_temperature_unit = entity_description.temperature_unit
        self._attr_min_temp = entity_description.min_temp
        self._attr_max_temp = entity_description.max_temp
        self._attr_operation_list = [STATE_OFF, STATE_ELECTRIC]

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to Home Assistant."""
        await super().async_added_to_hass()

        self._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self._attr_available:
            return self._attr_available

        return self.coordinator.last_update_success

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.connected:
            self._attr_available = False
        else:
            is_on = self.coordinator.device.is_on
            current_temperature = self.coordinator.get_data_value(
                self.entity_description.current_temperature_key
            )
            target_temperature = self.coordinator.get_setup_value(
                self.entity_description.target_temperature_key
            )
            if is_on is None or current_temperature is None:
                self._attr_available = False
            else:
                self._attr_current_operation = STATE_ELECTRIC if is_on else STATE_OFF
                self._attr_current_temperature = float(current_temperature)
                self._attr_target_temperature = (
                    float(target_temperature)
                    if target_temperature is not None
                    else None
                )
                self._attr_available = True

        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if not self.coordinator.connected:
            self._attr_available = False
        elif temperature is not None and await self.coordinator.set_setup_value(
            self.entity_description.target_temperature_key, float(temperature)
        ):
            self._attr_available = True
            self._attr_target_temperature = temperature
        else:
            _LOGGER.error("Failed to set %s", self.name)

        self.async_write_ha_state()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        if operation_mode == STATE_OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater on."""
        _LOGGER.debug("Turning on %s", self.name)

        if not self.coordinator.connected:
            self._attr_available = False
        elif await self.coordinator.device.turn_on():
            self._attr_available = True
            self._attr_current_operation = STATE_ELECTRIC
        else:
            _LOGGER.error("Failed to turn on %s", self.name)

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        _LOGGER.debug("Turning off %s", self.name)

        if not self.coordinator.connected:
            self._attr_available = False
        elif await self.coordinator.device.turn_off():
            self._attr_available = True
            self._attr_current_operation = STATE_OFF
        else:
            _LOGGER.error("Failed to turn off %s", self.name)

        self.async_write_ha_state()
