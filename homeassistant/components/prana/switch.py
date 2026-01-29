"""Switch platform for Prana integration."""

from collections.abc import Callable
from typing import Any

from aioesphomeapi import dataclass

from homeassistant.components.switch import (
    StrEnum,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PranaConfigEntry, PranaCoordinator
from .entity import PranaBaseEntity, PranaEntityDescription

PARALLEL_UPDATES = 1


class PranaSwitchType(StrEnum):
    """Enumerates Prana switch types exposed by the device API."""

    BOUND = "bound"
    HEATER = "heater"
    NIGHT = "night"
    BOOST = "boost"
    AUTO = "auto"
    AUTO_PLUS = "auto_plus"
    WINTER = "winter"


@dataclass(frozen=True, kw_only=True)
class PranaSwitchEntityDescription(SwitchEntityDescription, PranaEntityDescription):
    """Description of a Prana switch entity."""

    value_fn: Callable[[PranaCoordinator], bool]


ENTITIES: tuple[PranaEntityDescription, ...] = (
    PranaSwitchEntityDescription(
        key=PranaSwitchType.BOUND,
        translation_key="bound",
        value_fn=lambda coord: coord.data.bound,
    ),
    PranaSwitchEntityDescription(
        key=PranaSwitchType.HEATER,
        translation_key="heater",
        value_fn=lambda coord: coord.data.heater,
    ),
    PranaSwitchEntityDescription(
        key=PranaSwitchType.AUTO,
        translation_key="auto",
        value_fn=lambda coord: coord.data.auto,
    ),
    PranaSwitchEntityDescription(
        key=PranaSwitchType.AUTO_PLUS,
        translation_key="auto_plus",
        value_fn=lambda coord: coord.data.auto_plus,
    ),
    PranaSwitchEntityDescription(
        key=PranaSwitchType.WINTER,
        translation_key="winter",
        value_fn=lambda coord: coord.data.winter,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PranaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Prana switch entities from a config entry."""
    async_add_entities(
        PranaSwitch(entry.runtime_data, entity_description)
        for entity_description in ENTITIES
    )


class PranaSwitch(PranaBaseEntity, SwitchEntity):
    """Representation of a Prana switch (bound/heater/auto/etc)."""

    entity_description: PranaSwitchEntityDescription

    @property
    def is_on(self) -> bool:
        """Return switch on/off state."""
        return self.entity_description.value_fn(self.coordinator)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.api_client.set_switch(self.entity_description.key, True)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.api_client.set_switch(self.entity_description.key, False)
        await self.coordinator.async_refresh()
