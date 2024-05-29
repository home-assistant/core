"""Switch platform for Tessie integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tessie_api import (
    disable_sentry_mode,
    disable_valet_mode,
    enable_sentry_mode,
    enable_valet_mode,
    start_charging,
    start_defrost,
    start_steering_wheel_heater,
    stop_charging,
    stop_defrost,
    stop_steering_wheel_heater,
)

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TessieConfigEntry
from .coordinator import TessieStateUpdateCoordinator
from .entity import TessieEntity


@dataclass(frozen=True, kw_only=True)
class TessieSwitchEntityDescription(SwitchEntityDescription):
    """Describes Tessie Switch entity."""

    on_func: Callable
    off_func: Callable


DESCRIPTIONS: tuple[TessieSwitchEntityDescription, ...] = (
    TessieSwitchEntityDescription(
        key="charge_state_charge_enable_request",
        on_func=lambda: start_charging,
        off_func=lambda: stop_charging,
    ),
    TessieSwitchEntityDescription(
        key="climate_state_defrost_mode",
        on_func=lambda: start_defrost,
        off_func=lambda: stop_defrost,
    ),
    TessieSwitchEntityDescription(
        key="vehicle_state_sentry_mode",
        on_func=lambda: enable_sentry_mode,
        off_func=lambda: disable_sentry_mode,
    ),
    TessieSwitchEntityDescription(
        key="vehicle_state_valet_mode",
        on_func=lambda: enable_valet_mode,
        off_func=lambda: disable_valet_mode,
    ),
    TessieSwitchEntityDescription(
        key="climate_state_steering_wheel_heater",
        on_func=lambda: start_steering_wheel_heater,
        off_func=lambda: stop_steering_wheel_heater,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TessieConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tessie Switch platform from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        [
            TessieSwitchEntity(vehicle, description)
            for vehicle in data.vehicles
            for description in DESCRIPTIONS
            if description.key in vehicle.data
        ]
    )


class TessieSwitchEntity(TessieEntity, SwitchEntity):
    """Base class for Tessie Switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    entity_description: TessieSwitchEntityDescription

    def __init__(
        self,
        coordinator: TessieStateUpdateCoordinator,
        description: TessieSwitchEntityDescription,
    ) -> None:
        """Initialize the Switch."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the state of the Switch."""
        return self._value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Switch."""
        await self.run(self.entity_description.on_func())
        self.set((self.entity_description.key, True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Switch."""
        await self.run(self.entity_description.off_func())
        self.set((self.entity_description.key, False))
