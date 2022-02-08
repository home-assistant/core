"""Support for Overkiz switches."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState
from pyoverkiz.enums.ui import UIClass, UIWidget
from pyoverkiz.types import StateType as OverkizStateType

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantOverkizData
from .const import DOMAIN
from .entity import OverkizDescriptiveEntity


@dataclass
class OverkizSwitchDescriptionMixin:
    """Define an entity description mixin for switch entities."""

    turn_on: Callable[[Callable[..., Awaitable[None]]], Awaitable[None]]
    turn_off: Callable[[Callable[..., Awaitable[None]]], Awaitable[None]]


@dataclass
class OverkizSwitchDescription(SwitchEntityDescription, OverkizSwitchDescriptionMixin):
    """Class to describe an Overkiz switch."""

    is_on: Callable[[Callable[[str], OverkizStateType]], bool] | None = None


SWITCH_DESCRIPTIONS: list[OverkizSwitchDescription] = [
    OverkizSwitchDescription(
        key=UIWidget.DOMESTIC_HOT_WATER_TANK,
        turn_on=lambda execute_command: execute_command(
            OverkizCommand.SET_FORCE_HEATING, OverkizCommandParam.ON
        ),
        turn_off=lambda execute_command: execute_command(
            OverkizCommand.SET_FORCE_HEATING, OverkizCommandParam.OFF
        ),
        is_on=lambda select_state: (
            select_state(OverkizState.IO_FORCE_HEATING) == OverkizCommandParam.ON
        ),
        icon="mdi:water-boiler",
    ),
    OverkizSwitchDescription(
        key=UIClass.ON_OFF,
        turn_on=lambda execute_command: execute_command(OverkizCommand.ON),
        turn_off=lambda execute_command: execute_command(OverkizCommand.OFF),
        is_on=lambda select_state: (
            select_state(OverkizState.CORE_ON_OFF) == OverkizCommandParam.ON
        ),
        device_class=SwitchDeviceClass.OUTLET,
    ),
    OverkizSwitchDescription(
        key=UIClass.SWIMMING_POOL,
        turn_on=lambda execute_command: execute_command(OverkizCommand.ON),
        turn_off=lambda execute_command: execute_command(OverkizCommand.OFF),
        is_on=lambda select_state: (
            select_state(OverkizState.CORE_ON_OFF) == OverkizCommandParam.ON
        ),
        icon="mdi:pool",
    ),
    OverkizSwitchDescription(
        key=UIWidget.RTD_INDOOR_SIREN,
        turn_on=lambda execute_command: execute_command(OverkizCommand.ON),
        turn_off=lambda execute_command: execute_command(OverkizCommand.OFF),
        icon="mdi:bell",
    ),
    OverkizSwitchDescription(
        key=UIWidget.RTD_OUTDOOR_SIREN,
        turn_on=lambda execute_command: execute_command(OverkizCommand.ON),
        turn_off=lambda execute_command: execute_command(OverkizCommand.OFF),
        icon="mdi:bell",
    ),
    OverkizSwitchDescription(
        key=UIWidget.STATELESS_ALARM_CONTROLLER,
        turn_on=lambda execute_command: execute_command(OverkizCommand.ALARM_ON),
        turn_off=lambda execute_command: execute_command(OverkizCommand.ALARM_OFF),
        icon="mdi:shield-lock",
    ),
    OverkizSwitchDescription(
        key=UIWidget.STATELESS_EXTERIOR_HEATING,
        turn_on=lambda execute_command: execute_command(OverkizCommand.ON),
        turn_off=lambda execute_command: execute_command(OverkizCommand.OFF),
        icon="mdi:radiator",
    ),
]

SUPPORTED_DEVICES = {
    description.key: description for description in SWITCH_DESCRIPTIONS
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Overkiz switch from a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]
    entities: list[OverkizSwitch] = []

    for device in data.platforms[Platform.SWITCH]:
        if description := SUPPORTED_DEVICES.get(device.widget) or SUPPORTED_DEVICES.get(
            device.ui_class
        ):
            entities.append(
                OverkizSwitch(
                    device.device_url,
                    data.coordinator,
                    description,
                )
            )

    async_add_entities(entities)


class OverkizSwitch(OverkizDescriptiveEntity, SwitchEntity):
    """Representation of an Overkiz Switch."""

    entity_description: OverkizSwitchDescription

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        if self.entity_description.is_on:
            return self.entity_description.is_on(self.executor.select_state)

        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.turn_on(self.executor.async_execute_command)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_description.turn_off(self.executor.async_execute_command)
