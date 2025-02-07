"""Support for Overkiz (virtual) numbers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OverkizDataConfigEntry
from .const import IGNORED_OVERKIZ_DEVICES
from .coordinator import OverkizDataUpdateCoordinator
from .entity import OverkizDescriptiveEntity

BOOST_MODE_DURATION_DELAY = 1
OPERATING_MODE_DELAY = 3


@dataclass(frozen=True, kw_only=True)
class OverkizNumberDescription(NumberEntityDescription):
    """Class to describe an Overkiz number."""

    command: str

    min_value_state_name: str | None = None
    max_value_state_name: str | None = None
    inverted: bool = False
    set_native_value: (
        Callable[[float, Callable[..., Awaitable[None]]], Awaitable[None]] | None
    ) = None


async def _async_set_native_value_boost_mode_duration(
    value: float, execute_command: Callable[..., Awaitable[None]]
) -> None:
    """Update the boost duration value."""

    if value > 0:
        await execute_command(OverkizCommand.SET_BOOST_MODE_DURATION, value)
        await asyncio.sleep(
            BOOST_MODE_DURATION_DELAY
        )  # wait one second to not overload the device
        await execute_command(
            OverkizCommand.SET_CURRENT_OPERATING_MODE,
            {
                OverkizCommandParam.RELAUNCH: OverkizCommandParam.ON,
                OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF,
            },
        )
    else:
        await execute_command(
            OverkizCommand.SET_CURRENT_OPERATING_MODE,
            {
                OverkizCommandParam.RELAUNCH: OverkizCommandParam.OFF,
                OverkizCommandParam.ABSENCE: OverkizCommandParam.OFF,
            },
        )

    await asyncio.sleep(
        OPERATING_MODE_DELAY
    )  # wait 3 seconds to have the new duration in
    await execute_command(OverkizCommand.REFRESH_BOOST_MODE_DURATION)


NUMBER_DESCRIPTIONS: list[OverkizNumberDescription] = [
    # Cover: My Position (0 - 100)
    OverkizNumberDescription(
        key=OverkizState.CORE_MEMORIZED_1_POSITION,
        name="My position",
        icon="mdi:content-save-cog",
        command=OverkizCommand.SET_MEMORIZED_1_POSITION,
        native_min_value=0,
        native_max_value=100,
        entity_category=EntityCategory.CONFIG,
    ),
    # WaterHeater: Expected Number Of Shower (2 - 4)
    OverkizNumberDescription(
        key=OverkizState.CORE_EXPECTED_NUMBER_OF_SHOWER,
        name="Expected number of shower",
        icon="mdi:shower-head",
        command=OverkizCommand.SET_EXPECTED_NUMBER_OF_SHOWER,
        native_min_value=2,
        native_max_value=4,
        min_value_state_name=OverkizState.CORE_MINIMAL_SHOWER_MANUAL_MODE,
        max_value_state_name=OverkizState.CORE_MAXIMAL_SHOWER_MANUAL_MODE,
        entity_category=EntityCategory.CONFIG,
    ),
    OverkizNumberDescription(
        key=OverkizState.CORE_TARGET_DWH_TEMPERATURE,
        name="Target temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        command=OverkizCommand.SET_TARGET_DHW_TEMPERATURE,
        native_min_value=50,
        native_max_value=65,
        min_value_state_name=OverkizState.CORE_MINIMAL_TEMPERATURE_MANUAL_MODE,
        max_value_state_name=OverkizState.CORE_MAXIMAL_TEMPERATURE_MANUAL_MODE,
        entity_category=EntityCategory.CONFIG,
    ),
    OverkizNumberDescription(
        key=OverkizState.CORE_WATER_TARGET_TEMPERATURE,
        name="Water target temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        command=OverkizCommand.SET_WATER_TARGET_TEMPERATURE,
        native_min_value=50,
        native_max_value=65,
        min_value_state_name=OverkizState.CORE_MINIMAL_TEMPERATURE_MANUAL_MODE,
        max_value_state_name=OverkizState.CORE_MAXIMAL_TEMPERATURE_MANUAL_MODE,
        entity_category=EntityCategory.CONFIG,
    ),
    # SomfyHeatingTemperatureInterface
    OverkizNumberDescription(
        key=OverkizState.CORE_ECO_ROOM_TEMPERATURE,
        name="Eco room temperature",
        icon="mdi:thermometer",
        command=OverkizCommand.SET_ECO_TEMPERATURE,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=6,
        native_max_value=29,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
    ),
    OverkizNumberDescription(
        key=OverkizState.CORE_COMFORT_ROOM_TEMPERATURE,
        name="Comfort room temperature",
        icon="mdi:home-thermometer-outline",
        command=OverkizCommand.SET_COMFORT_TEMPERATURE,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=7,
        native_max_value=30,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
    ),
    OverkizNumberDescription(
        key=OverkizState.CORE_SECURED_POSITION_TEMPERATURE,
        name="Freeze protection temperature",
        icon="mdi:sun-thermometer-outline",
        command=OverkizCommand.SET_SECURED_POSITION_TEMPERATURE,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=5,
        native_max_value=15,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
    ),
    # DimmerExteriorHeating (Somfy Terrace Heater) (0 - 100)
    # Needs to be inverted since 100 = off, 0 = on
    OverkizNumberDescription(
        key=OverkizState.CORE_LEVEL,
        icon="mdi:patio-heater",
        command=OverkizCommand.SET_LEVEL,
        native_min_value=0,
        native_max_value=100,
        inverted=True,
    ),
    # DomesticHotWaterProduction - boost mode duration in days (0 - 7)
    OverkizNumberDescription(
        key=OverkizState.CORE_BOOST_MODE_DURATION,
        name="Boost mode duration",
        icon="mdi:water-boiler",
        command=OverkizCommand.SET_BOOST_MODE_DURATION,
        native_min_value=0,
        native_max_value=7,
        set_native_value=_async_set_native_value_boost_mode_duration,
        entity_category=EntityCategory.CONFIG,
    ),
    # DomesticHotWaterProduction - away mode in days (0 - 6)
    OverkizNumberDescription(
        key=OverkizState.IO_AWAY_MODE_DURATION,
        name="Away mode duration",
        icon="mdi:water-boiler-off",
        command=OverkizCommand.SET_AWAY_MODE_DURATION,
        native_min_value=0,
        native_max_value=6,
        entity_category=EntityCategory.CONFIG,
    ),
]

SUPPORTED_STATES = {description.key: description for description in NUMBER_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Overkiz number from a config entry."""
    data = entry.runtime_data
    entities: list[OverkizNumber] = []

    for device in data.coordinator.data.values():
        if (
            device.widget in IGNORED_OVERKIZ_DEVICES
            or device.ui_class in IGNORED_OVERKIZ_DEVICES
        ):
            continue

        entities.extend(
            OverkizNumber(
                device.device_url,
                data.coordinator,
                description,
            )
            for state in device.definition.states
            if (description := SUPPORTED_STATES.get(state.qualified_name))
        )

    async_add_entities(entities)


class OverkizNumber(OverkizDescriptiveEntity, NumberEntity):
    """Representation of an Overkiz Number."""

    entity_description: OverkizNumberDescription

    def __init__(
        self,
        device_url: str,
        coordinator: OverkizDataUpdateCoordinator,
        description: OverkizNumberDescription,
    ) -> None:
        """Initialize a device."""
        super().__init__(device_url, coordinator, description)

        if self.entity_description.min_value_state_name and (
            state := self.device.states.get(
                self.entity_description.min_value_state_name
            )
        ):
            self._attr_native_min_value = cast(float, state.value)

        if self.entity_description.max_value_state_name and (
            state := self.device.states.get(
                self.entity_description.max_value_state_name
            )
        ):
            self._attr_native_max_value = cast(float, state.value)

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        if state := self.device.states.get(self.entity_description.key):
            if self.entity_description.inverted:
                return self.native_max_value - cast(float, state.value)

            return cast(float, state.value)

        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.inverted:
            value = self.native_max_value - value

        if self.entity_description.set_native_value:
            await self.entity_description.set_native_value(
                value, self.executor.async_execute_command
            )
            return

        await self.executor.async_execute_command(
            self.entity_description.command, value
        )
