"""Water heater platform for Qube Heat Pump."""

from typing import Any

from homeassistant.components.water_heater import (
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import QubeConfigEntry
from .const import DOMAIN
from .coordinator import QubeCoordinator
from .entity import QubeEntity

PARALLEL_UPDATES = 1

DHW_BOOST_KEY = "tapw_timeprogram_bms_forced"
DHW_SETPOINT_KEY = "setpoint_dhw"
DHW_MIN_TEMP = 40
DHW_MAX_TEMP = 65

OPERATION_MODES = [STATE_HEAT_PUMP, STATE_PERFORMANCE]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Qube water heater."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([QubeWaterHeater(coordinator, entry)])


class QubeWaterHeater(QubeEntity, WaterHeaterEntity):
    """Qube DHW water heater entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = DHW_MIN_TEMP
    _attr_max_temp = DHW_MAX_TEMP
    _attr_operation_list = OPERATION_MODES
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_translation_key = "water_heater"

    def __init__(
        self,
        coordinator: QubeCoordinator,
        entry: QubeConfigEntry,
    ) -> None:
        """Initialize the water heater."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = entry.entry_id

    @property
    def current_temperature(self) -> float | None:
        """Return the current DHW temperature."""
        return self.coordinator.data.state.temp_dhw

    @property
    def target_temperature(self) -> float | None:
        """Return the target DHW temperature."""
        return self.coordinator.data.state.setpoint_dhw

    @property
    def current_operation(self) -> str | None:
        """Return the current operation mode."""
        boost = self.coordinator.data.switches.get(DHW_BOOST_KEY)
        if boost is None:
            return None
        if boost:
            return STATE_PERFORMANCE
        return STATE_HEAT_PUMP

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target DHW temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        try:
            success = await self.coordinator.client.write_setpoint(
                DHW_SETPOINT_KEY, temperature
            )
        except (ConnectionError, TimeoutError, OSError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_temperature_failed",
            ) from err
        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_temperature_failed",
            )
        await self.coordinator.async_request_refresh()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set the operation mode."""
        boost = operation_mode == STATE_PERFORMANCE
        try:
            success = await self.coordinator.client.write_switch(DHW_BOOST_KEY, boost)
        except (ConnectionError, TimeoutError, OSError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_command_failed",
            ) from err
        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_command_failed",
            )
        await self.coordinator.async_request_refresh()
