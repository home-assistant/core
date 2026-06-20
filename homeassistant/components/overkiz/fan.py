"""Support for Overkiz ventilation systems as fans."""

from dataclasses import dataclass
from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizState, UIWidget

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
class OverkizVentilationPointDescription(FanEntityDescription):
    """Class to describe an Overkiz ventilation point fan."""

    current_air_flow_state: OverkizState
    set_air_flow_command: OverkizCommand


# The three IO ventilation point widgets are identical apart from the
# command/state used to read and set the air flow level (0-100).
VENTILATION_POINT_DESCRIPTIONS: dict[UIWidget, OverkizVentilationPointDescription] = {
    UIWidget.VENTILATION_INLET: OverkizVentilationPointDescription(
        key="ventilation_inlet",
        current_air_flow_state=OverkizState.CORE_AIR_INPUT,
        set_air_flow_command=OverkizCommand.SET_AIR_INPUT,
    ),
    UIWidget.VENTILATION_OUTLET: OverkizVentilationPointDescription(
        key="ventilation_outlet",
        current_air_flow_state=OverkizState.CORE_AIR_OUTPUT,
        set_air_flow_command=OverkizCommand.SET_AIR_OUTPUT,
    ),
    UIWidget.VENTILATION_TRANSFER: OverkizVentilationPointDescription(
        key="ventilation_transfer",
        current_air_flow_state=OverkizState.CORE_AIR_TRANSFER,
        set_air_flow_command=OverkizCommand.SET_AIR_TRANSFER,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Overkiz fans from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        OverkizVentilationPointFan(
            device.device_url,
            data.coordinator,
            VENTILATION_POINT_DESCRIPTIONS[device.widget],
        )
        for device in data.platforms[Platform.FAN]
        if device.widget in VENTILATION_POINT_DESCRIPTIONS
    )


class OverkizVentilationPointFan(OverkizDescriptiveEntity, FanEntity):
    """Representation of an Overkiz IO ventilation point as a fan."""

    entity_description: OverkizVentilationPointDescription

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
        """Return whether the ventilation point is running."""
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
        """Turn the ventilation point on."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return

        await self.executor.async_execute_command(OverkizCommand.ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the ventilation point off."""
        await self.executor.async_execute_command(OverkizCommand.OFF)
