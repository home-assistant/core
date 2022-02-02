"""Switch platform for Advantage Air integration."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ADVANTAGE_AIR_STATE_OFF,
    ADVANTAGE_AIR_STATE_ON,
    DOMAIN as ADVANTAGE_AIR_DOMAIN,
)
from .entity import AdvantageAirEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir toggle platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities = []
    for ac_key, ac_device in instance["coordinator"].data["aircons"].items():
        if ac_device["info"]["freshAirStatus"] != "none":
            entities.append(AdvantageAirFreshAir(instance, ac_key))
    async_add_entities(entities)


class AdvantageAirFreshAir(AdvantageAirEntity, SwitchEntity):
    """Representation of Advantage Air fresh air control."""

    _attr_icon = "mdi:air-filter"

    def __init__(self, instance, ac_key):
        """Initialize an Advantage Air fresh air control."""
        super().__init__(instance, ac_key)
        self._attr_name = f'{self._ac["name"]} Fresh Air'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{ac_key}-freshair'
        )

    @property
    def is_on(self):
        """Return the fresh air status."""
        return self._ac["freshAirStatus"] == ADVANTAGE_AIR_STATE_ON

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
