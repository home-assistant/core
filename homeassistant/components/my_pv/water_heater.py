"""Creates Water Heater entities for the my-PV Home Assistant integration."""

from typing import Any, override

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

from .const import DOMAIN
from .coordinator import MyPVConfigEntry, MyPVCoordinator
from .entity import MyPVDataEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyPVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV water heater."""
    coordinator = config_entry.runtime_data
    entities = []

    if (
        coordinator.device.is_on is not None
        and coordinator.device.current_temperature is not None
        and (configuration := coordinator.device.get_setup_configuration("ww1target"))
    ):
        entity_description = WaterHeaterEntityDescription(
            key="water_heater",
        )
        entities.append(
            MyPVWaterHeater(
                coordinator,
                entity_description,
                coordinator.device.serial_number,
                configuration=configuration["unit"],
            )
        )

    async_add_entities(entities)


class MyPVWaterHeater(MyPVDataEntity, WaterHeaterEntity):
    """my-PV water heater."""

    _attr_name = None
    _attr_operation_list = [STATE_OFF, STATE_ELECTRIC]
    _attr_supported_features = (
        WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    def __init__(
        self,
        coordinator: MyPVCoordinator,
        entity_description: WaterHeaterEntityDescription,
        serial_number: str,
        configuration: dict[str, Any],
    ) -> None:
        """Initialize the water_heater."""
        super().__init__(coordinator, entity_description, serial_number)

        self._attr_target_temperature_step = configuration["step"]
        self._attr_temperature_unit = configuration["unit"]
        self._attr_min_temp = configuration["max"]
        self._attr_max_temp = configuration["min"]

    @property
    @override
    def current_operation(self) -> str | None:
        """Return current operation."""
        return STATE_ELECTRIC if self.coordinator.device.is_on else STATE_OFF

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.device.current_temperature

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.coordinator.device.target_temperature

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if not await self.coordinator.set_target_temperature(
            float(kwargs[ATTR_TEMPERATURE])
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )

    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        if operation_mode == STATE_OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater on."""
        if not await self.coordinator.turn_on():
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        if not await self.coordinator.turn_off():
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )
