from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)

from frisquet_connect.const import WATER_HEATER_TRANSLATIONS_KEY, SanitaryWaterModeLabel
from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)
from frisquet_connect.entities.core_entity import CoreEntity


class DefaultWaterHeaterEntity(CoreEntity, WaterHeaterEntity):

    def __init__(self, coordinator: FrisquetConnectCoordinator) -> None:
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{self.coordinator.data.site_id}_{WATER_HEATER_TRANSLATIONS_KEY}"
        )
        self._attr_has_entity_name = True
        self._attr_translation_key = WATER_HEATER_TRANSLATIONS_KEY

        self._attr_supported_features = WaterHeaterEntityFeature.OPERATION_MODE
        self._attr_temperature_unit = "°C"
        self._attr_operation_list = coordinator.data.available_sanitary_water_modes

    def update(self) -> None:
        self.current_operation = SanitaryWaterModeLabel[
            self.coordinator.data.water_heater.sanitary_water_mode.name
        ]

    async def async_turn_on(self) -> None:
        """Turn the water heater on."""
        await self.async_set_operation_mode(SanitaryWaterModeLabel.ECO_TIMER)

    async def async_turn_off(self) -> None:
        """Turn the water heater off."""
        await self.async_set_operation_mode(SanitaryWaterModeLabel.STOP)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        await self.coordinator.service.async_set_sanitary_water_mode(
            self.coordinator.data.site_id, operation_mode
        )

        await self.coordinator.async_request_refresh()
