"""The water heater platform for the A. O. Smith integration."""

from typing import Any

from py_aosmith.models import OperationMode as AOSmithOperationMode

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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AOSmithData
from .const import DOMAIN
from .coordinator import AOSmithStatusCoordinator
from .entity import AOSmithStatusEntity

MODE_HA_TO_AOSMITH = {
    STATE_ECO: AOSmithOperationMode.HYBRID,
    STATE_ELECTRIC: AOSmithOperationMode.ELECTRIC,
    STATE_HEAT_PUMP: AOSmithOperationMode.HEAT_PUMP,
    STATE_OFF: AOSmithOperationMode.VACATION,
}
MODE_AOSMITH_TO_HA = {
    AOSmithOperationMode.ELECTRIC: STATE_ELECTRIC,
    AOSmithOperationMode.HEAT_PUMP: STATE_HEAT_PUMP,
    AOSmithOperationMode.HYBRID: STATE_ECO,
    AOSmithOperationMode.VACATION: STATE_OFF,
}

# Priority list for operation mode to use when exiting away mode
# Will use the first mode that is supported by the device
DEFAULT_OPERATION_MODE_PRIORITY = [
    AOSmithOperationMode.HYBRID,
    AOSmithOperationMode.HEAT_PUMP,
    AOSmithOperationMode.ELECTRIC,
]


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
        ha_modes = []
        for supported_mode in self.device.supported_modes:
            ha_mode = MODE_AOSMITH_TO_HA.get(supported_mode.mode)

            # Filtering out STATE_OFF since it is handled by away mode
            if ha_mode is not None and ha_mode != STATE_OFF:
                ha_modes.append(ha_mode)

        return ha_modes

    @property
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Return the list of supported features."""
        supports_vacation_mode = any(
            supported_mode.mode == AOSmithOperationMode.VACATION
            for supported_mode in self.device.supported_modes
        )

        support_flags = WaterHeaterEntityFeature.TARGET_TEMPERATURE

        # Operation mode only supported if there is more than one mode
        if len(self.operation_list) > 1:
            support_flags |= WaterHeaterEntityFeature.OPERATION_MODE

        if supports_vacation_mode:
            support_flags |= WaterHeaterEntityFeature.AWAY_MODE

        return support_flags

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.device.status.temperature_setpoint

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.device.status.temperature_setpoint_maximum

    @property
    def current_operation(self) -> str:
        """Return the current operation mode."""
        return MODE_AOSMITH_TO_HA.get(self.device.status.current_mode, STATE_OFF)

    @property
    def is_away_mode_on(self):
        """Return True if away mode is on."""
        return self.device.status.current_mode == AOSmithOperationMode.VACATION

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        if operation_mode not in self.operation_list:
            raise HomeAssistantError("Operation mode not supported")

        aosmith_mode = MODE_HA_TO_AOSMITH.get(operation_mode)
        if aosmith_mode is not None:
            await self.client.update_mode(self.junction_id, aosmith_mode)

            await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is not None:
            await self.client.update_setpoint(self.junction_id, temperature)

            await self.coordinator.async_request_refresh()

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        await self.client.update_mode(self.junction_id, AOSmithOperationMode.VACATION)

        await self.coordinator.async_request_refresh()

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        supported_aosmith_modes = [x.mode for x in self.device.supported_modes]

        for mode in DEFAULT_OPERATION_MODE_PRIORITY:
            if mode in supported_aosmith_modes:
                await self.client.update_mode(self.junction_id, mode)
                break
