"""Platform for eq3 switch entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from eq3btsmart import Thermostat
from eq3btsmart.models import Status

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Eq3ConfigEntry
from .const import ENTITY_KEY_AWAY, ENTITY_KEY_BOOST, ENTITY_KEY_LOCK
from .entity import Eq3Entity


@dataclass(frozen=True, kw_only=True)
class Eq3SwitchEntityDescription(SwitchEntityDescription):
    """Entity description for eq3 switch entities."""

    toggle_func: Callable[[Thermostat], Callable[[bool], Awaitable[None]]]
    value_func: Callable[[Status], bool]


SWITCH_ENTITY_DESCRIPTIONS = [
    Eq3SwitchEntityDescription(
        key=ENTITY_KEY_LOCK,
        translation_key=ENTITY_KEY_LOCK,
        toggle_func=lambda thermostat: thermostat.async_set_locked,
        value_func=lambda status: status.is_locked,
    ),
    Eq3SwitchEntityDescription(
        key=ENTITY_KEY_BOOST,
        translation_key=ENTITY_KEY_BOOST,
        toggle_func=lambda thermostat: thermostat.async_set_boost,
        value_func=lambda status: status.is_boost,
    ),
    Eq3SwitchEntityDescription(
        key=ENTITY_KEY_AWAY,
        translation_key=ENTITY_KEY_AWAY,
        toggle_func=lambda thermostat: thermostat.async_set_away,
        value_func=lambda status: status.is_away,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Eq3ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the entry."""

    async_add_entities(
        Eq3SwitchEntity(entry, entity_description)
        for entity_description in SWITCH_ENTITY_DESCRIPTIONS
    )


class Eq3SwitchEntity(Eq3Entity, SwitchEntity):
    """Base class for eq3 switch entities."""

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
        """Turn on the switch."""

        await self.entity_description.toggle_func(self._thermostat)(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""

        await self.entity_description.toggle_func(self._thermostat)(False)

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""

        if TYPE_CHECKING:
            assert self._thermostat.status is not None

        return self.entity_description.value_func(self._thermostat.status)
