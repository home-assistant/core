"""Support for Overkiz fans."""

from dataclasses import dataclass
from typing import Any, cast, override

from pyoverkiz.enums import OverkizCommand, OverkizState
from pyoverkiz.enums.ui import UIWidget

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OverkizDataConfigEntry
from .entity import OverkizDescriptiveEntity


@dataclass(frozen=True, kw_only=True)
class OverkizFanDescription(FanEntityDescription):
    """Class to describe an Overkiz fan."""

    percentage: OverkizState
    set_percentage: OverkizCommand


FAN_DESCRIPTIONS: list[OverkizFanDescription] = [
    OverkizFanDescription(
        key=UIWidget.VENTILATION_INLET,
        percentage=OverkizState.CORE_AIR_INPUT,
        set_percentage=OverkizCommand.SET_AIR_INPUT,
    ),
    OverkizFanDescription(
        key=UIWidget.VENTILATION_OUTLET,
        percentage=OverkizState.CORE_AIR_OUTPUT,
        set_percentage=OverkizCommand.SET_AIR_OUTPUT,
    ),
    OverkizFanDescription(
        key=UIWidget.VENTILATION_TRANSFER,
        percentage=OverkizState.CORE_AIR_TRANSFER,
        set_percentage=OverkizCommand.SET_AIR_TRANSFER,
    ),
]

SUPPORTED_DEVICES = {description.key: description for description in FAN_DESCRIPTIONS}


PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Overkiz fans from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        OverkizFan(
            device.device_url,
            data.coordinator,
            description,
        )
        for device in data.platforms[Platform.FAN]
        if (
            description := SUPPORTED_DEVICES.get(device.widget)
            or SUPPORTED_DEVICES.get(device.ui_class)
        )
    )


class OverkizFan(OverkizDescriptiveEntity, FanEntity):
    """Representation of an Overkiz fan."""

    entity_description: OverkizFanDescription

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    @property
    @override
    def percentage(self) -> int | None:
        """Return the current air flow level as a percentage."""
        air_flow = self.device.states.get_value(self.entity_description.percentage)

        if air_flow is None:
            return None

        return cast(int, air_flow)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the fan is running."""
        if (percentage := self.percentage) is None:
            return None

        return percentage > 0

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the air flow level."""
        if percentage == 0:
            await self.async_turn_off()
            return

        await self.executor.async_execute_command(
            self.entity_description.set_percentage, percentage
        )

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return

        await self.executor.async_execute_command(OverkizCommand.ON)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.executor.async_execute_command(OverkizCommand.OFF)
