"""Select platform for Advantage Air integration."""
from typing import cast

from advantage_air import advantage_air

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as ADVANTAGE_AIR_DOMAIN
from .entity import AdvantageAirEntity

ADVANTAGE_AIR_INACTIVE = "Inactive"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir toggle platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities = []
    for ac_key in instance["coordinator"].data["aircons"]:
        entities.append(AdvantageAirMyZone(instance, ac_key))
    async_add_entities(entities)


class AdvantageAirMyZone(AdvantageAirEntity, SelectEntity):
    """Representation of Advantage Air MyZone control."""

    _attr_icon = "mdi:home-thermometer"
    _attr_options = [ADVANTAGE_AIR_INACTIVE]
    _number_to_name = {0: ADVANTAGE_AIR_INACTIVE}
    _name_to_number = {ADVANTAGE_AIR_INACTIVE: 0}

    def __init__(self, instance: advantage_air, ac_key: int) -> None:
        """Initialize an Advantage Air MyZone control."""
        super().__init__(instance, ac_key)
        self._attr_name = f'{self._ac["name"]} MyZone'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{ac_key}-myzone'
        )

        for zone in instance["coordinator"].data["aircons"][ac_key]["zones"].values():
            if zone["type"] > 0:
                self._name_to_number[zone["name"]] = zone["number"]
                self._number_to_name[zone["number"]] = zone["name"]
                self._attr_options.append(zone["name"])

    @property
    def current_option(self) -> str:
        """Return the fresh air status."""
        return self._number_to_name[cast(int, self._ac["myZone"])]

    async def async_select_option(self, option: str) -> None:
        """Set the MyZone."""
        await self.async_change(
            {self.ac_key: {"info": {"myZone": self._name_to_number[option]}}}
        )
