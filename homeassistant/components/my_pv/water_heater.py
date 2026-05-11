"""Creates Water Heater entities for the my-PV Home Assistant integration."""

import logging
from typing import Any

from homeassistant.components.water_heater import (
    STATE_ELECTRIC,
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MyPVConfigEntry, MyPVCoordinator
from .const import DOMAIN
from .entity import MyPVBaseEntity

_LOGGER = logging.getLogger(__name__)


CURRENT_TEMPERATURE_KEY = "temp1"
TARGET_TEMPERATURE_KEY = "ww1target"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyPVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV water heater."""
    coordinator = config_entry.runtime_data
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
            key="temp1",
            temperature_unit=target_temperature_config["unit"],
            target_temperature_step=target_temperature_config["step"],
            max_temp=target_temperature_config["max"],
            min_temp=target_temperature_config["min"],
        )
        entities.append(
            MyPVWaterHeater(
                coordinator,
                entity_description,
                coordinator.device.serial_number,
            )
        )

    async_add_entities(entities)


class MyPVWaterHeaterEntityDescription(
    WaterHeaterEntityDescription, frozen_or_thawed=True
):
    """A class that describes my-PV water heater entities."""

    target_temperature_step: float
    max_temp: float
    min_temp: float
    temperature_unit: str


class MyPVWaterHeater(MyPVBaseEntity, WaterHeaterEntity):
    """Base my-PV WaterHeater."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_operation_list = [STATE_OFF, STATE_ELECTRIC]
    _attr_supported_features = (
        WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    entity_description: MyPVWaterHeaterEntityDescription

    def __init__(
        self,
        coordinator: MyPVCoordinator,
        entity_description: MyPVWaterHeaterEntityDescription,
        serial_number: str,
    ) -> None:
        """Initialize the water_heater."""
        super().__init__(coordinator, entity_description.key)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{serial_number}-{entity_description.key}"

        self.entity_description = entity_description

        self._attr_target_temperature_step = entity_description.target_temperature_step
        self._attr_temperature_unit = entity_description.temperature_unit
        self._attr_min_temp = entity_description.min_temp
        self._attr_max_temp = entity_description.max_temp

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.connected:
            return False
        if self.coordinator.get_data_value(CURRENT_TEMPERATURE_KEY) is None:
            return False

        return super().available

    @property
    def current_operation(self) -> str | None:
        """Return current operation."""
        return STATE_ELECTRIC if self.coordinator.device.is_on else STATE_OFF

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        current_temperature = self.coordinator.get_data_value(CURRENT_TEMPERATURE_KEY)
        return float(current_temperature) if current_temperature is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        target_temperature = self.coordinator.get_setup_value(TARGET_TEMPERATURE_KEY)
        return float(target_temperature) if target_temperature is not None else None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temperature is not None and await self.coordinator.set_setup_value(
            TARGET_TEMPERATURE_KEY, float(temperature)
        ):
            self.async_write_ha_state()
        else:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        if operation_mode == STATE_OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater on."""
        _LOGGER.debug("Turning on %s", self.name)

        if await self.coordinator.turn_on():
            self._attr_current_operation = STATE_ELECTRIC
            self.async_write_ha_state()
        else:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        _LOGGER.debug("Turning off %s", self.name)

        if await self.coordinator.turn_off():
            self._attr_current_operation = STATE_OFF
            self.async_write_ha_state()
        else:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )
