"""Plugwise water heater component for Home Assistant."""

from dataclasses import dataclass
from typing import Any, Final, override

from homeassistant.components.water_heater import (
    STATE_GAS,
    STATE_HEAT_PUMP,
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    DHW_TEMP,
    DOMAIN,
    LOWER_BOUND,
    UPPER_BOUND,
    BinarySensorType,
    WaterHeaterType,
)
from .coordinator import PlugwiseConfigEntry, PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import plugwise_command

PARALLEL_UPDATES = 0

FAIL_SET_TEMP: Final = "temperature_out_of_range"
OPERATION_LIST: Final[list[str]] = [STATE_GAS, STATE_HEAT_PUMP, STATE_OFF]


@dataclass(frozen=True, kw_only=True)
class PlugwiseWaterHeaterEntityDescription(WaterHeaterEntityDescription):
    """Class describing Plugwise WaterHeater entities."""

    key: WaterHeaterType
    state_key: BinarySensorType


WATERHEATER_TYPES = (
    PlugwiseWaterHeaterEntityDescription(
        key=DHW_TEMP,
        translation_key=DHW_TEMP,
        state_key="dhw_state",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlugwiseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Plugwise water_heater from a config entry."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities() -> None:
        """Add Entities."""
        if not coordinator.new_devices:
            return

        async_add_entities(
            PlugwiseWaterHeaterEntity(coordinator, device_id, description)
            for device_id in coordinator.new_devices
            for description in WATERHEATER_TYPES
            if description.key in coordinator.data[device_id]
        )

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


class PlugwiseWaterHeaterEntity(PlugwiseEntity, WaterHeaterEntity):
    """Representation of a Plugwise water heater."""

    entity_description: PlugwiseWaterHeaterEntityDescription

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
        description: PlugwiseWaterHeaterEntityDescription,
    ) -> None:
        """Initialise the water_heater."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_max_temp = self.device[description.key][UPPER_BOUND]
        self._attr_min_temp = self.device[description.key][LOWER_BOUND]
        self._attr_operation_list = OPERATION_LIST
        self._attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
        self._attr_target_temperature_step = max(
            self.device[description.key]["resolution"], 1.0
        )
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_unique_id = f"{device_id}-{description.key}"

    @property
    @override
    def current_operation(self) -> str:
        """Return current readable operation mode."""
        if (
            binary_sensors := self.device.get("binary_sensors", {})
        ) and binary_sensors.get(self.entity_description.state_key, False):
            if "outdoor_air_temperature" in self.device["sensors"]:
                if binary_sensors.get("secondary_boiler_state", False):
                    return STATE_GAS

                return STATE_HEAT_PUMP

            return STATE_GAS

        return STATE_OFF

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current water temperature."""
        return self.device[self.entity_description.key].get("current")

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the water temperature we try to reach."""
        return self.device[self.entity_description.key].get("setpoint")

    @plugwise_command
    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = float(kwargs[ATTR_TEMPERATURE])
        if temperature < self._attr_min_temp or temperature > self._attr_max_temp:
            temperature_unit = self.hass.config.units.temperature_unit
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=FAIL_SET_TEMP,
                translation_placeholders={
                    "temperature": str(temperature),
                    "max_temp": str(
                        TemperatureConverter.convert(
                            self._attr_max_temp,
                            UnitOfTemperature.CELSIUS,
                            temperature_unit,
                        )
                    ),
                    "min_temp": str(
                        TemperatureConverter.convert(
                            self._attr_min_temp,
                            UnitOfTemperature.CELSIUS,
                            temperature_unit,
                        )
                    ),
                    "temperature_unit": temperature_unit,
                },
            )

        await self.coordinator.api.set_number(
            self._dev_id,
            self.entity_description.key,
            temperature,
        )
