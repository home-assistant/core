"""Support for water heaters through the SmartThings cloud API."""

from __future__ import annotations

from typing import Any

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity

OPERATION_MAP_TO_HA: dict[str, str] = {
    "eco": "eco",
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
                Capability.AIR_CONDITIONER_MODE,
                Capability.TEMPERATURE_MEASUREMENT,
                Capability.CUSTOM_THERMOSTAT_SETPOINT_CONTROL,
                Capability.THERMOSTAT_COOLING_SETPOINT,
                Capability.SAMSUNG_CE_EHS_THERMOSTAT,
            )
        )
    )


class SmartThingsWaterHeater(SmartThingsEntity, WaterHeaterEntity):
    """Define a SmartThings Water Heater."""

    _attr_name = None
    _attr_supported_features = (
        WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.TARGET_TEMPERATURE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, client: SmartThings, device: FullDevice) -> None:
        """Init the class."""
        super().__init__(
            client,
            device,
            {
                Capability.AIR_CONDITIONER_MODE,
                Capability.TEMPERATURE_MEASUREMENT,
                Capability.CUSTOM_THERMOSTAT_SETPOINT_CONTROL,
                Capability.THERMOSTAT_COOLING_SETPOINT,
            },
        )

    @property
    def operation_list(self) -> list[str]:
        """Return the list of available operation modes."""
        modes = self.get_attribute_value(
            Capability.AIR_CONDITIONER_MODE, Attribute.SUPPORTED_AC_MODES
        )
        return [
            OPERATION_MAP_TO_HA[mode] for mode in modes if mode in OPERATION_MAP_TO_HA
        ]

    @property
    def current_operation(self) -> str | None:
        """Return the current operation mode."""
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
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.get_attribute_value(
            Capability.CUSTOM_THERMOSTAT_SETPOINT_CONTROL, Attribute.MINIMUM_SETPOINT
        )

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.get_attribute_value(
            Capability.CUSTOM_THERMOSTAT_SETPOINT_CONTROL, Attribute.MAXIMUM_SETPOINT
        )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        await self.execute_device_command(
            Capability.AIR_CONDITIONER_MODE,
            Command.SET_AIR_CONDITIONER_MODE,
            argument=operation_mode,
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self.execute_device_command(
            Capability.THERMOSTAT_COOLING_SETPOINT,
            Command.SET_COOLING_SETPOINT,
            argument=kwargs[ATTR_TEMPERATURE],
        )
