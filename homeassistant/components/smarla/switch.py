"""Support for the Swing2Sleep Smarla switch entities."""

from dataclasses import dataclass
from typing import Any

from pysmarlaapi import Federwiege
from pysmarlaapi.federwiege.classes import Property

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FederwiegeConfigEntry
from .entity import SmarlaBaseEntity


@dataclass(frozen=True, kw_only=True)
class SmarlaSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Swing2Sleep Smarla switch entity."""

    service: str
    property: str


SWITCHES: list[SmarlaSwitchEntityDescription] = [
    SmarlaSwitchEntityDescription(
        key="cradle",
        name=None,
        service="babywiege",
        property="swing_active",
    ),
    SmarlaSwitchEntityDescription(
        key="smartmode",
        translation_key="smartmode",
        service="babywiege",
        property="smartmode",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FederwiegeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Smarla switches from config entry."""
    federwiege: Federwiege = config_entry.runtime_data
    async_add_entities(SmarlaSwitch(federwiege, desc) for desc in SWITCHES)


class SmarlaSwitch(SmarlaBaseEntity, SwitchEntity):
    """Representation of Smarla switch."""

    entity_description: SmarlaSwitchEntityDescription
    _property: Property
    _attr_should_poll = False

    async def on_change(self, value: Any):
        """Notify ha when state changes."""
        self.async_write_ha_state()

    def __init__(
        self,
        federwiege: Federwiege,
        description: SmarlaSwitchEntityDescription,
    ) -> None:
        """Initialize a Smarla switch."""
        super().__init__(federwiege)
        self._property = federwiege.get_service(description.service).get_property(
            description.property
        )
        self.entity_description = description
        self._attr_unique_id = f"{federwiege.serial_number}-{description.key}"

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        await self._property.add_listener(self.on_change)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        await self._property.remove_listener(self.on_change)

    @property
    def is_on(self) -> bool:
        """Return the entity value to represent the entity state."""
        return self._property.get()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._property.set(True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._property.set(False)
