"""Switch platform for Habitica integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    HabiticaConfigEntry,
    HabiticaData,
    HabiticaDataUpdateCoordinator,
)
from .entity import HabiticaBase

PARALLEL_UPDATES = 1


@dataclass(kw_only=True, frozen=True)
class HabiticaSwitchEntityDescription(SwitchEntityDescription):
    """Describes Habitica switch entity."""

    turn_on_fn: Callable[[HabiticaDataUpdateCoordinator], Any]
    turn_off_fn: Callable[[HabiticaDataUpdateCoordinator], Any]
    is_on_fn: Callable[[HabiticaData], bool | None]


class HabiticaSwitchEntity(StrEnum):
    """Habitica switch entities."""

    SLEEP = "sleep"


SWTICH_DESCRIPTIONS: tuple[HabiticaSwitchEntityDescription, ...] = (
    HabiticaSwitchEntityDescription(
        key=HabiticaSwitchEntity.SLEEP,
        translation_key=HabiticaSwitchEntity.SLEEP,
        device_class=SwitchDeviceClass.SWITCH,
        turn_on_fn=lambda coordinator: coordinator.habitica.toggle_sleep(),
        turn_off_fn=lambda coordinator: coordinator.habitica.toggle_sleep(),
        is_on_fn=lambda data: data.user.preferences.sleep,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HabiticaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches from a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        HabiticaSwitch(coordinator, description) for description in SWTICH_DESCRIPTIONS
    )


class HabiticaSwitch(HabiticaBase, SwitchEntity):
    """Representation of a Habitica Switch."""

    entity_description: HabiticaSwitchEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return self.entity_description.is_on_fn(
            self.coordinator.data,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""

        await self.coordinator.execute(self.entity_description.turn_on_fn)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""

        await self.coordinator.execute(self.entity_description.turn_off_fn)
