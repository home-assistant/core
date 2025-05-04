"""Switch platform for Miele switch integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Final, cast

import aiohttp
from pymiele import MieleDevice

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    DOMAIN,
    POWER_OFF,
    POWER_ON,
    PROCESS_ACTION,
    MieleActions,
    MieleAppliance,
    StateStatus,
)
from .coordinator import MieleConfigEntry
from .entity import MieleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MieleSwitchDescription(SwitchEntityDescription):
    """Class describing Miele switch entities."""

    value_fn: Callable[[MieleDevice], StateType]
    on_value: int = 0
    off_value: int = 0
    on_cmd_data: dict[str, str | int | bool]
    off_cmd_data: dict[str, str | int | bool]


@dataclass
class MieleSwitchDefinition:
    """Class for defining switch entities."""

    types: tuple[MieleAppliance, ...]
    description: MieleSwitchDescription


SWITCH_TYPES: Final[tuple[MieleSwitchDefinition, ...]] = (
    MieleSwitchDefinition(
        types=(MieleAppliance.FRIDGE, MieleAppliance.FRIDGE_FREEZER),
        description=MieleSwitchDescription(
            key="supercooling",
            value_fn=lambda value: value.state_status,
            on_value=StateStatus.SUPERCOOLING,
            translation_key="supercooling",
            on_cmd_data={PROCESS_ACTION: MieleActions.START_SUPERCOOL},
            off_cmd_data={PROCESS_ACTION: MieleActions.STOP_SUPERCOOL},
        ),
    ),
    MieleSwitchDefinition(
        types=(
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.WINE_CABINET_FREEZER,
        ),
        description=MieleSwitchDescription(
            key="superfreezing",
            value_fn=lambda value: value.state_status,
            on_value=StateStatus.SUPERFREEZING,
            translation_key="superfreezing",
            on_cmd_data={PROCESS_ACTION: MieleActions.START_SUPERFREEZE},
            off_cmd_data={PROCESS_ACTION: MieleActions.STOP_SUPERFREEZE},
        ),
    ),
    MieleSwitchDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.DISH_WARMER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.COFFEE_SYSTEM,
            MieleAppliance.HOOD,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleSwitchDescription(
            key="poweronoff",
            value_fn=lambda value: value.state_status,
            off_value=1,
            translation_key="power",
            on_cmd_data={POWER_ON: True},
            off_cmd_data={POWER_OFF: True},
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MieleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator = config_entry.runtime_data

    def _async_add_new_devices(new_devices: dict[str, MieleDevice]) -> None:
        entities: list = []
        entity_class: type[MieleSwitch]
        for device_id, device in new_devices.items():
            for definition in SWITCH_TYPES:
                if device.device_type in definition.types:
                    match definition.description.key:
                        case "poweronoff":
                            entity_class = MielePowerSwitch
                        case "supercooling" | "superfreezing":
                            entity_class = MieleSuperSwitch

                    entities.append(
                        entity_class(coordinator, device_id, definition.description)
                    )
        async_add_entities(entities)

    coordinator.new_device_callbacks.append(_async_add_new_devices)
    _async_add_new_devices(coordinator.data.devices)


class MieleSwitch(MieleEntity, SwitchEntity):
    """Representation of a Switch."""

    entity_description: MieleSwitchDescription

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        await self.async_turn_switch(self.entity_description.on_cmd_data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        await self.async_turn_switch(self.entity_description.off_cmd_data)

    async def async_turn_switch(self, mode: dict[str, str | int | bool]) -> None:
        """Set switch to mode."""
        try:
            await self.api.send_action(self._device_id, mode)
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_state_error",
                translation_placeholders={
                    "entity": self.entity_id,
                },
            ) from err


class MielePowerSwitch(MieleSwitch):
    """Representation of a power switch."""

    entity_description: MieleSwitchDescription

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return self.action.power_off_enabled

    @property
    def available(self) -> bool:
        """Return the availability of the entity."""

        return (
            self.action.power_off_enabled or self.action.power_on_enabled
        ) and super().available

    async def async_turn_switch(self, mode: dict[str, str | int | bool]) -> None:
        """Set switch to mode."""
        try:
            await self.api.send_action(self._device_id, mode)
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_state_error",
                translation_placeholders={
                    "entity": self.entity_id,
                },
            ) from err
        self.action.power_on_enabled = cast(bool, mode)
        self.action.power_off_enabled = not cast(bool, mode)
        self.async_write_ha_state()


class MieleSuperSwitch(MieleSwitch):
    """Representation of a supercool/superfreeze switch."""

    entity_description: MieleSwitchDescription

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return (
            self.entity_description.value_fn(self.device)
            == self.entity_description.on_value
        )
