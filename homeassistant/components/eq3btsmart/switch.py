"""Platform for eq3 lock entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from eq3btsmart import Thermostat
from eq3btsmart.models import Status

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Eq3ConfigEntry
from .const import (
    ENTITY_ICON_AWAY,
    ENTITY_ICON_BOOST,
    ENTITY_KEY_AWAY,
    ENTITY_KEY_BOOST,
    ENTITY_KEY_LOCK,
)
from .entity import Eq3Entity


@dataclass(frozen=True, kw_only=True)
class Eq3SwitchEntityDescription(SwitchEntityDescription):
    """Entity description for eq3 switch entities."""

    turn_on_func: Callable[[Thermostat], Awaitable[None]]
    turn_off_func: Callable[[Thermostat], Awaitable[None]]
    value_func: Callable[[Status], bool]


async def async_lock(thermostat: Thermostat) -> None:
    """Lock the thermostat."""

    await thermostat.async_set_locked(True)


async def async_unlock(thermostat: Thermostat) -> None:
    """Unlock the thermostat."""

    await thermostat.async_set_locked(False)


async def async_boost_enable(thermostat: Thermostat) -> None:
    """Enable the boost mode."""

    await thermostat.async_set_boost(True)


async def async_boost_disable(thermostat: Thermostat) -> None:
    """Disable the boost mode."""

    await thermostat.async_set_boost(False)


async def async_away_enable(thermostat: Thermostat) -> None:
    """Enable the away mode."""

    await thermostat.async_set_away(True)


async def async_away_disable(thermostat: Thermostat) -> None:
    """Disable the away mode."""

    await thermostat.async_set_away(False)


SWITCH_ENTITY_DESCRIPTIONS = [
    Eq3SwitchEntityDescription(
        key=ENTITY_KEY_LOCK,
        translation_key=ENTITY_KEY_LOCK,
        turn_on_func=async_lock,
        turn_off_func=async_unlock,
        value_func=lambda status: status.is_locked,
    ),
    Eq3SwitchEntityDescription(
        key=ENTITY_KEY_BOOST,
        translation_key=ENTITY_KEY_BOOST,
        turn_on_func=async_boost_enable,
        turn_off_func=async_boost_disable,
        value_func=lambda status: status.is_boost,
        icon=ENTITY_ICON_BOOST,
    ),
    Eq3SwitchEntityDescription(
        key=ENTITY_KEY_AWAY,
        translation_key=ENTITY_KEY_AWAY,
        turn_on_func=async_away_enable,
        turn_off_func=async_away_disable,
        value_func=lambda status: status.is_away,
        icon=ENTITY_ICON_AWAY,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Eq3ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the entry."""

    async_add_entities(
        Eq3SwitchEntity(entry, entity_description)
        for entity_description in SWITCH_ENTITY_DESCRIPTIONS
    )


class Eq3SwitchEntity(Eq3Entity, SwitchEntity):
    """Lock to prevent manual changes to the thermostat."""

    entity_description: Eq3SwitchEntityDescription

    def __init__(
        self,
        entry: Eq3ConfigEntry,
        entity_description: Eq3SwitchEntityDescription,
    ) -> None:
        """Initialize the entity."""

        super().__init__(entry, entity_description.key)
        self.entity_description = entity_description

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Lock the thermostat."""

        await self.entity_description.turn_on_func(self._thermostat)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unlock the thermostat."""

        await self.entity_description.turn_off_func(self._thermostat)

    @property
    def is_on(self) -> bool:
        """Whether the thermostat is locked."""

        if TYPE_CHECKING:
            assert self._thermostat.status is not None

        return self.entity_description.value_func(self._thermostat.status)
