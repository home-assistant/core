"""Platform for eq3 switch entities."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from typing import Any

from eq3btsmart import Thermostat
from eq3btsmart.const import EQ3_DEFAULT_AWAY_TEMP, Eq3OperationMode
from eq3btsmart.models import Status

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
import homeassistant.util.dt as dt_util

from . import Eq3ConfigEntry
from .const import (
    DEFAULT_AWAY_HOURS,
    ENTITY_KEY_AWAY,
    ENTITY_KEY_BOOST,
    ENTITY_KEY_LOCK,
)
from .entity import Eq3Entity


async def async_set_away(thermostat: Thermostat, enable: bool) -> Status:
    """Backport old async_set_away behavior."""
    if not enable:
        return await thermostat.async_set_mode(Eq3OperationMode.AUTO)

    away_until = dt_util.now() + timedelta(hours=DEFAULT_AWAY_HOURS)
    return await thermostat.async_set_away(away_until, EQ3_DEFAULT_AWAY_TEMP)


@dataclass(frozen=True, kw_only=True)
class Eq3SwitchEntityDescription(SwitchEntityDescription):
    """Entity description for eq3 switch entities."""

    toggle_func: Callable[[Thermostat], Callable[[bool], Coroutine[None, None, Status]]]
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
        toggle_func=lambda thermostat: partial(async_set_away, thermostat),
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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.entity_description.value_func(self.coordinator.data)
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.entity_description.toggle_func(self._thermostat)(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.entity_description.toggle_func(self._thermostat)(False)
