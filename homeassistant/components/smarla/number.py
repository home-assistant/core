"""Support for the Swing2Sleep Smarla number entities."""

from dataclasses import dataclass
from typing import Any

from pysmarlaapi import Federwiege

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FederwiegeConfigEntry
from .entity import SmarlaBaseEntity


@dataclass(frozen=True, kw_only=True)
class SmarlaNumberEntityDescription(NumberEntityDescription):
    """Class describing Swing2Sleep Smarla number entities."""

    service: str
    property: str


NUMBER_TYPES: list[SmarlaNumberEntityDescription] = [
    SmarlaNumberEntityDescription(
        key="intensity",
        translation_key="intensity",
        service="babywiege",
        property="intensity",
        native_max_value=100,
        native_min_value=0,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FederwiegeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Smarla numbers from config entry."""
    federwiege = config_entry.runtime_data

    entities: list[NumberEntity] = []

    for desc in NUMBER_TYPES:
        entity = SmarlaNumber(federwiege, desc)
        entities.append(entity)

    async_add_entities(entities)


class SmarlaNumber(SmarlaBaseEntity, NumberEntity):
    """Representation of Smarla number."""

    async def on_change(self, value: Any):
        """Notify ha when state changes."""
        self.async_write_ha_state()

    def __init__(
        self,
        federwiege: Federwiege,
        description: SmarlaNumberEntityDescription,
    ) -> None:
        """Initialize a Smarla number."""
        super().__init__(federwiege)
        self.property = federwiege.get_service(description.service).get_property(
            description.property
        )
        self.entity_description = description
        self._attr_should_poll = False
        self._attr_unique_id = f"{federwiege.serial_number}-{description.key}"

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        await self.property.add_listener(self.on_change)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        await self.property.remove_listener(self.on_change)

    @property
    def native_value(self) -> float:
        """Return the entity value to represent the entity state."""
        return self.property.get()

    def set_native_value(self, value: float) -> None:
        """Update to the smarla device."""
        self.property.set(int(value))
