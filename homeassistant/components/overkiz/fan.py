"""Support for Overkiz fans."""

from dataclasses import dataclass
from typing import Any, cast

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

    current_air_flow_state: OverkizState
    set_air_flow_command: OverkizCommand


FAN_DESCRIPTIONS: list[OverkizFanDescription] = [
    # IO ventilation points: identical apart from the command/state used
    # to read and set the air flow level (0-100).
    OverkizFanDescription(
        key=UIWidget.VENTILATION_INLET,
        current_air_flow_state=OverkizState.CORE_AIR_INPUT,
        set_air_flow_command=OverkizCommand.SET_AIR_INPUT,
    ),
    OverkizFanDescription(
        key=UIWidget.VENTILATION_OUTLET,
        current_air_flow_state=OverkizState.CORE_AIR_OUTPUT,
        set_air_flow_command=OverkizCommand.SET_AIR_OUTPUT,
    ),
    OverkizFanDescription(
        key=UIWidget.VENTILATION_TRANSFER,
        current_air_flow_state=OverkizState.CORE_AIR_TRANSFER,
        set_air_flow_command=OverkizCommand.SET_AIR_TRANSFER,
    ),
]

SUPPORTED_DEVICES = {description.key: description for description in FAN_DESCRIPTIONS}


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
    def percentage(self) -> int | None:
        """Return the current air flow level as a percentage."""
        air_flow = self.device.states.get_value(
            self.entity_description.current_air_flow_state
        )

        if air_flow is None:
            return None

        return cast(int, air_flow)

    @property
    def is_on(self) -> bool | None:
        """Return whether the fan is running."""
        if (percentage := self.percentage) is None:
            return None

        return percentage > 0

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the air flow level."""
        if percentage == 0:
            await self.async_turn_off()
            return

        await self.executor.async_execute_command(
            self.entity_description.set_air_flow_command, percentage
        )

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

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.executor.async_execute_command(OverkizCommand.OFF)
