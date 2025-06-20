"""Support for the Swing2Sleep Smarla number entities."""

from dataclasses import dataclass

from pysmarlaapi.federwiege.classes import Property

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FederwiegeConfigEntry
from .entity import SmarlaBaseEntity, SmarlaEntityDescription


@dataclass(frozen=True, kw_only=True)
class SmarlaNumberEntityDescription(SmarlaEntityDescription, NumberEntityDescription):
    """Class describing Swing2Sleep Smarla number entities."""


NUMBERS: list[SmarlaNumberEntityDescription] = [
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
    async_add_entities(SmarlaNumber(federwiege, desc) for desc in NUMBERS)


class SmarlaNumber(SmarlaBaseEntity, NumberEntity):
    """Representation of Smarla number."""

    entity_description: SmarlaNumberEntityDescription

    _property: Property[int]

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        v = self._property.get()
        return float(v) if v is not None else None

    def set_native_value(self, value: float) -> None:
        """Update to the smarla device."""
        self._property.set(int(value))
