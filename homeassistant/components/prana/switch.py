"""Switch platform for Prana integration."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PranaConfigEntry, PranaCoordinator
from .entity import PranaBaseEntity

PARALLEL_UPDATES = 1


class PranaSwitchType(StrEnum):
    """Enumerates Prana switch types exposed by the device API."""

    HEATER = "heater"
    WINTER = "winter"


@dataclass(frozen=True, kw_only=True)
class PranaSwitchEntityDescription(SwitchEntityDescription):
    """Description of a Prana switch entity."""

    key: PranaSwitchType
    value_fn: Callable[[PranaCoordinator], bool]


# Heater and winter are anti-ice protections that run alongside the operating
# mode (auto, night, etc.) and are therefore toggles, not preset modes.
ENTITIES: tuple[PranaSwitchEntityDescription, ...] = (
    PranaSwitchEntityDescription(
        key=PranaSwitchType.HEATER,
        translation_key="heater",
        value_fn=lambda coord: coord.data.heater,
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
    """Representation of a Prana switch."""

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
