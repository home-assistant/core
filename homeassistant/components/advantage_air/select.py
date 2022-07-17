"""Select platform for Advantage Air integration."""
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ADVANTAGE_AIR_AIRCONS,
    ADVANTAGE_AIR_COORDINATOR,
    DOMAIN as ADVANTAGE_AIR_DOMAIN,
)
from .entity import AdvantageAirAirconEntity

ADVANTAGE_AIR_INACTIVE = "Inactive"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir select platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities = []
    if ADVANTAGE_AIR_AIRCONS in instance[ADVANTAGE_AIR_COORDINATOR].data:
        for ac_key in instance[ADVANTAGE_AIR_COORDINATOR].data[ADVANTAGE_AIR_AIRCONS]:
            entities.append(AdvantageAirMyZone(instance, ac_key))
    async_add_entities(entities)


class AdvantageAirMyZone(AdvantageAirAirconEntity, SelectEntity):
    """Representation of Advantage Air MyZone control."""

    _attr_icon = "mdi:home-thermometer"
    _attr_options = [ADVANTAGE_AIR_INACTIVE]
    _number_to_name = {0: ADVANTAGE_AIR_INACTIVE}
    _name_to_number = {ADVANTAGE_AIR_INACTIVE: 0}

    def __init__(self, instance, ac_key):
        """Initialize an Advantage Air MyZone control."""
        super().__init__(instance, ac_key)
        self._attr_name = f'{self._ac["name"]} myZone'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{ac_key}-myzone'
        )

        for zone in (
            instance[ADVANTAGE_AIR_COORDINATOR]
            .data["aircons"][ac_key]["zones"]
            .values()
        ):
            if zone["type"] > 0:
                self._name_to_number[zone["name"]] = zone["number"]
                self._number_to_name[zone["number"]] = zone["name"]
                self._attr_options.append(zone["name"])

    @property
    def current_option(self):
        """Return the current MyZone."""
        return self._number_to_name[self._ac["myZone"]]

    async def async_select_option(self, option):
        """Set the MyZone."""
        await self.async_set_aircon(
            {self.ac_key: {"info": {"myZone": self._name_to_number[option]}}}
        )
