"""Platform for Miele switch integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Final

import aiohttp

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    POWER_OFF,
    POWER_ON,
    PROCESS_ACTION,
    MieleActions,
    MieleAppliance,
    StateStatus,
)
from .coordinator import MieleConfigEntry, MieleDataUpdateCoordinator
from .entity import MieleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MieleSwitchDescription(SwitchEntityDescription):
    """Class describing Miele switch entities."""

    data_tag: str
    on_value: int = 0
    off_value: int = 0
    on_data: dict[str, str | int | bool]
    off_data: dict[str, str | int | bool]


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
            data_tag="state_status",
            on_value=StateStatus.SUPERCOOLING,
            icon="mdi:snowflake",
            translation_key="supercooling",
            on_data={PROCESS_ACTION: MieleActions.START_SUPERCOOL},
            off_data={PROCESS_ACTION: MieleActions.STOP_SUPERCOOL},
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
            data_tag="state_status",
            on_value=StateStatus.SUPERFREEZING,
            icon="mdi:snowflake",
            translation_key="superfreezing",
            on_data={PROCESS_ACTION: MieleActions.START_SUPERFREEZE},
            off_data={PROCESS_ACTION: MieleActions.STOP_SUPERFREEZE},
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
            data_tag="state_status",
            off_value=1,
            icon="mdi:power",
            translation_key="power_on",
            on_data={POWER_ON: True},
            off_data={POWER_OFF: True},
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

    entities = [
        MieleSwitch(coordinator, device_id, definition.description)
        for device_id in coordinator.data.devices
        for definition in SWITCH_TYPES
        if coordinator.data.devices[device_id].device_type in definition.types
    ]

    async_add_entities(entities)


class MieleSwitch(MieleEntity, SwitchEntity):
    """Representation of a Switch."""

    entity_description: MieleSwitchDescription

    def __init__(
        self,
        coordinator: MieleDataUpdateCoordinator,
        device_id,
        description: MieleSwitchDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_id, description)
        self._api = coordinator.api

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        if self.entity_description.key in {"supercooling", "superfreezing"}:
            return (
                getattr(
                    self.coordinator.data.devices[self._device_id],
                    self.entity_description.data_tag,
                )
                == self.entity_description.on_value
            )

        if self.entity_description.key in {"poweronoff"}:
            return self.coordinator.data.actions[self._device_id].power_off_enabled

        return False

    @property
    def available(self) -> bool:
        """Return the availability of the entity."""

        if self.entity_description.key in {"poweronoff"}:
            avail = (
                self.coordinator.data.actions[self._device_id].power_off_enabled
                or self.coordinator.data.actions[self._device_id].power_on_enabled
            )
        else:
            avail = True

        return super().available and avail

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        await self._async_turn_switch(self.entity_description.on_data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        await self._async_turn_switch(self.entity_description.off_data)

    async def _async_turn_switch(self, mode: dict[str, str | int | bool]) -> None:
        """Set switch to mode."""
        try:
            await self._api.send_action(self._device_id, mode)
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_switch_error",
                translation_placeholders={
                    "entity": self.entity_id,
                },
            ) from err
