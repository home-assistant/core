"""Switch platform for Prana integration."""

from typing import Any

from homeassistant.components.switch import (
    StrEnum,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PranaConfigEntry
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


class PranaSwitchEntityDescription(SwitchEntityDescription, PranaEntityDescription):
    """Description of a Prana switch entity."""


ENTITIES: tuple[PranaEntityDescription, ...] = (
    PranaSwitchEntityDescription(
        key=PranaSwitchType.BOUND,
        translation_key="bound",
    ),
    PranaSwitchEntityDescription(
        key=PranaSwitchType.HEATER,
        translation_key="heater",
    ),
    PranaSwitchEntityDescription(
        key=PranaSwitchType.AUTO,
        translation_key="auto",
    ),
    PranaSwitchEntityDescription(
        key=PranaSwitchType.AUTO_PLUS,
        translation_key="auto_plus",
    ),
    PranaSwitchEntityDescription(
        key=PranaSwitchType.WINTER,
        translation_key="winter",
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

    @property
    def is_on(self) -> bool:
        """Return switch on/off state."""
        value = getattr(self.coordinator.data, self.entity_description.key, False)
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._entry.runtime_data.api_client.set_switch(
            self.entity_description.key, True
        )
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._entry.runtime_data.api_client.set_switch(
            self.entity_description.key, False
        )
        await self.coordinator.async_refresh()
