"""Support for the Swing2Sleep Smarla switch entities."""

from dataclasses import dataclass
from typing import Any

from pysmarlaapi.federwiege.classes import Property

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FederwiegeConfigEntry
from .entity import SmarlaBaseEntity, SmarlaEntityDescription


@dataclass(frozen=True, kw_only=True)
class SmarlaSwitchEntityDescription(SmarlaEntityDescription, SwitchEntityDescription):
    """Class describing Swing2Sleep Smarla switch entity."""


SWITCHES: list[SmarlaSwitchEntityDescription] = [
    SmarlaSwitchEntityDescription(
        key="swing_active",
        name=None,
        service="babywiege",
        property="swing_active",
    ),
    SmarlaSwitchEntityDescription(
        key="smart_mode",
        translation_key="smart_mode",
        service="babywiege",
        property="smart_mode",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FederwiegeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Smarla switches from config entry."""
    federwiege = config_entry.runtime_data
    async_add_entities(SmarlaSwitch(federwiege, desc) for desc in SWITCHES)


class SmarlaSwitch(SmarlaBaseEntity, SwitchEntity):
    """Representation of Smarla switch."""

    entity_description: SmarlaSwitchEntityDescription

    _property: Property[bool]

    @property
    def is_on(self) -> bool | None:
        """Return the entity value to represent the entity state."""
        return self._property.get()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._property.set(True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._property.set(False)
