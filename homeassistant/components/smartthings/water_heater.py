"""Support for water heaters through the SmartThings cloud API."""

from __future__ import annotations

from typing import Any

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.water_heater import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    STATE_ECO,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN, UNIT_MAP
from .entity import SmartThingsEntity

OPERATION_MAP_TO_HA: dict[str, str] = {
    "eco": STATE_ECO,
    "std": "standard",
    "force": "force",
    "power": "power",
}

HA_TO_OPERATION_MAP = {v: k for k, v in OPERATION_MAP_TO_HA.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add water heaters for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsWaterHeater(entry_data.client, device)
        for device in entry_data.devices.values()
        if all(
            capability in device.status[MAIN]
            for capability in (
                Capability.SWITCH,
                Capability.AIR_CONDITIONER_MODE,
                Capability.TEMPERATURE_MEASUREMENT,
                Capability.CUSTOM_THERMOSTAT_SETPOINT_CONTROL,
                Capability.THERMOSTAT_COOLING_SETPOINT,
                Capability.SAMSUNG_CE_EHS_THERMOSTAT,
                Capability.CUSTOM_OUTING_MODE,
            )
        )
        and device.status[MAIN][Capability.TEMPERATURE_MEASUREMENT][
            Attribute.TEMPERATURE
        ].value
        is not None
    )


class SmartThingsWaterHeater(SmartThingsEntity, WaterHeaterEntity):
    """Define a SmartThings Water Heater."""

    _attr_name = None
    _attr_translation_key = "water_heater"

    def __init__(self, client: SmartThings, device: FullDevice) -> None:
        """Init the class."""
        super().__init__(
            client,
            device,
            {
                Capability.SWITCH,
                Capability.AIR_CONDITIONER_MODE,
                Capability.TEMPERATURE_MEASUREMENT,
                Capability.CUSTOM_THERMOSTAT_SETPOINT_CONTROL,
                Capability.THERMOSTAT_COOLING_SETPOINT,
                Capability.CUSTOM_OUTING_MODE,
            },
        )
        unit = self._internal_state[Capability.TEMPERATURE_MEASUREMENT][
            Attribute.TEMPERATURE
        ].unit
        assert unit is not None
        self._attr_temperature_unit = UNIT_MAP[unit]

    @property
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Return the supported features."""
        features = (
            WaterHeaterEntityFeature.OPERATION_MODE
            | WaterHeaterEntityFeature.AWAY_MODE
            | WaterHeaterEntityFeature.ON_OFF
        )
        if self.get_attribute_value(Capability.SWITCH, Attribute.SWITCH) == "on":
            features |= WaterHeaterEntityFeature.TARGET_TEMPERATURE
        return features

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        min_temperature = TemperatureConverter.convert(
            DEFAULT_MIN_TEMP, UnitOfTemperature.FAHRENHEIT, self._attr_temperature_unit
        )
        return min(min_temperature, self.target_temperature_low)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        max_temperature = TemperatureConverter.convert(
            DEFAULT_MAX_TEMP, UnitOfTemperature.FAHRENHEIT, self._attr_temperature_unit
        )
        return max(max_temperature, self.target_temperature_high)

    @property
    def operation_list(self) -> list[str]:
        """Return the list of available operation modes."""
        return [
            STATE_OFF,
            *(
                OPERATION_MAP_TO_HA[mode]
                for mode in self.get_attribute_value(
                    Capability.AIR_CONDITIONER_MODE, Attribute.SUPPORTED_AC_MODES
                )
                if mode in OPERATION_MAP_TO_HA
            ),
        ]

    @property
    def current_operation(self) -> str | None:
        """Return the current operation mode."""
        if self.get_attribute_value(Capability.SWITCH, Attribute.SWITCH) == "off":
            return STATE_OFF
        return OPERATION_MAP_TO_HA.get(
            self.get_attribute_value(
                Capability.AIR_CONDITIONER_MODE, Attribute.AIR_CONDITIONER_MODE
            )
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.get_attribute_value(
            Capability.TEMPERATURE_MEASUREMENT, Attribute.TEMPERATURE
        )

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self.get_attribute_value(
            Capability.THERMOSTAT_COOLING_SETPOINT, Attribute.COOLING_SETPOINT
        )

    @property
    def target_temperature_low(self) -> float:
        """Return the minimum temperature."""
        return self.get_attribute_value(
            Capability.CUSTOM_THERMOSTAT_SETPOINT_CONTROL, Attribute.MINIMUM_SETPOINT
        )

    @property
    def target_temperature_high(self) -> float:
        """Return the maximum temperature."""
        return self.get_attribute_value(
            Capability.CUSTOM_THERMOSTAT_SETPOINT_CONTROL, Attribute.MAXIMUM_SETPOINT
        )

    @property
    def is_away_mode_on(self) -> bool:
        """Return if away mode is on."""
        return (
            self.get_attribute_value(
                Capability.CUSTOM_OUTING_MODE, Attribute.OUTING_MODE
            )
            == "on"
        )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        if operation_mode == STATE_OFF:
            await self.async_turn_off()
            return
        if self.current_operation == STATE_OFF:
            await self.async_turn_on()
        await self.execute_device_command(
            Capability.AIR_CONDITIONER_MODE,
            Command.SET_AIR_CONDITIONER_MODE,
            argument=HA_TO_OPERATION_MAP[operation_mode],
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self.execute_device_command(
            Capability.THERMOSTAT_COOLING_SETPOINT,
            Command.SET_COOLING_SETPOINT,
            argument=kwargs[ATTR_TEMPERATURE],
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater on."""
        await self.execute_device_command(
            Capability.SWITCH,
            Command.ON,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        await self.execute_device_command(
            Capability.SWITCH,
            Command.OFF,
        )

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        await self.execute_device_command(
            Capability.CUSTOM_OUTING_MODE,
            Command.SET_OUTING_MODE,
            argument="on",
        )

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        await self.execute_device_command(
            Capability.CUSTOM_OUTING_MODE,
            Command.SET_OUTING_MODE,
            argument="off",
        )
