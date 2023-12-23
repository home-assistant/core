"""The water heater platform for the A. O. Smith integration."""

from typing import Any

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_HEAT_PUMP,
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AOSmithData
from .const import (
    AOSMITH_MODE_ELECTRIC,
    AOSMITH_MODE_HEAT_PUMP,
    AOSMITH_MODE_HYBRID,
    AOSMITH_MODE_VACATION,
    DOMAIN,
)
from .coordinator import AOSmithStatusCoordinator
from .entity import AOSmithStatusEntity

MODE_HA_TO_AOSMITH = {
    STATE_OFF: AOSMITH_MODE_VACATION,
    STATE_ECO: AOSMITH_MODE_HYBRID,
    STATE_ELECTRIC: AOSMITH_MODE_ELECTRIC,
    STATE_HEAT_PUMP: AOSMITH_MODE_HEAT_PUMP,
}
MODE_AOSMITH_TO_HA = {
    AOSMITH_MODE_ELECTRIC: STATE_ELECTRIC,
    AOSMITH_MODE_HEAT_PUMP: STATE_HEAT_PUMP,
    AOSMITH_MODE_HYBRID: STATE_ECO,
    AOSMITH_MODE_VACATION: STATE_OFF,
}

# Operation mode to use when exiting away mode
DEFAULT_OPERATION_MODE = AOSMITH_MODE_HYBRID

DEFAULT_SUPPORT_FLAGS = (
    WaterHeaterEntityFeature.TARGET_TEMPERATURE
    | WaterHeaterEntityFeature.OPERATION_MODE
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up A. O. Smith water heater platform."""
    data: AOSmithData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        AOSmithWaterHeaterEntity(data.status_coordinator, junction_id)
        for junction_id in data.status_coordinator.data
    )


class AOSmithWaterHeaterEntity(AOSmithStatusEntity, WaterHeaterEntity):
    """The water heater entity for the A. O. Smith integration."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = 95

    def __init__(
        self,
        coordinator: AOSmithStatusCoordinator,
        junction_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, junction_id)
        self._attr_unique_id = junction_id

    @property
    def operation_list(self) -> list[str]:
        """Return the list of supported operation modes."""
        op_modes = []
        for mode_dict in self.device_data.get("modes", []):
            mode_name = mode_dict.get("mode")
            ha_mode = MODE_AOSMITH_TO_HA.get(mode_name)

            # Filtering out STATE_OFF since it is handled by away mode
            if ha_mode is not None and ha_mode != STATE_OFF:
                op_modes.append(ha_mode)

        return op_modes

    @property
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Return the list of supported features."""
        supports_vacation_mode = any(
            mode_dict.get("mode") == AOSMITH_MODE_VACATION
            for mode_dict in self.device_data.get("modes", [])
        )

        if supports_vacation_mode:
            return DEFAULT_SUPPORT_FLAGS | WaterHeaterEntityFeature.AWAY_MODE

        return DEFAULT_SUPPORT_FLAGS

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.device_data.get("temperatureSetpoint")

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.device_data.get("temperatureSetpointMaximum")

    @property
    def current_operation(self) -> str:
        """Return the current operation mode."""
        return MODE_AOSMITH_TO_HA.get(self.device_data.get("mode"), STATE_OFF)

    @property
    def is_away_mode_on(self):
        """Return True if away mode is on."""
        return self.device_data.get("mode") == AOSMITH_MODE_VACATION

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        aosmith_mode = MODE_HA_TO_AOSMITH.get(operation_mode)
        if aosmith_mode is not None:
            await self.client.update_mode(self.junction_id, aosmith_mode)

        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        await self.client.update_setpoint(self.junction_id, temperature)

        await self.coordinator.async_request_refresh()

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        await self.client.update_mode(self.junction_id, AOSMITH_MODE_VACATION)

        await self.coordinator.async_request_refresh()

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        await self.client.update_mode(self.junction_id, DEFAULT_OPERATION_MODE)

        await self.coordinator.async_request_refresh()
