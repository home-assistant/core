"""Switch platform for Advantage Air integration."""

from homeassistant.helpers.entity import ToggleEntity

from .const import (
    ADVANTAGE_AIR_STATE_OFF,
    ADVANTAGE_AIR_STATE_ON,
    DOMAIN as ADVANTAGE_AIR_DOMAIN,
)
from .entity import AdvantageAirEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AdvantageAir toggle platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities = []
    for ac_key, ac_device in instance["coordinator"].data["aircons"].items():
        if ac_device["info"]["freshAirStatus"] != "none":
            entities.append(AdvantageAirFreshAir(instance, ac_key))
    async_add_entities(entities)


class AdvantageAirFreshAir(AdvantageAirEntity, ToggleEntity):
    """Representation of Advantage Air fresh air control."""

    @property
    def name(self):
        """Return the name."""
        return f'{self._ac["name"]} Fresh Air'

    @property
    def unique_id(self):
        """Return a unique id."""
        return f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-freshair'

    @property
    def is_on(self):
        """Return the fresh air status."""
        return self._ac["freshAirStatus"] == ADVANTAGE_AIR_STATE_ON

    @property
    def icon(self):
        """Return a representative icon of the fresh air switch."""
        return "mdi:air-filter"

    async def async_turn_on(self, **kwargs):
        """Turn fresh air on."""
        await self.async_change(
            {self.ac_key: {"info": {"freshAirStatus": ADVANTAGE_AIR_STATE_ON}}}
        )

    async def async_turn_off(self, **kwargs):
        """Turn fresh air off."""
        await self.async_change(
            {self.ac_key: {"info": {"freshAirStatus": ADVANTAGE_AIR_STATE_OFF}}}
        )
