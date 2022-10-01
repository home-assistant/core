"""Switch platform for Advantage Air integration."""
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ADVANTAGE_AIR_STATE_OFF,
    ADVANTAGE_AIR_STATE_ON,
    DOMAIN as ADVANTAGE_AIR_DOMAIN,
)
from .entity import AdvantageAirAcEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir switch platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities: list[SwitchEntity] = []
    if aircons := instance["coordinator"].data.get("aircons"):
        for ac_key, ac_device in aircons.items():
            if ac_device["info"]["freshAirStatus"] != "none":
                entities.append(AdvantageAirFreshAir(instance, ac_key))
    async_add_entities(entities)


class AdvantageAirFreshAir(AdvantageAirAcEntity, SwitchEntity):
    """Representation of Advantage Air fresh air control."""

    _attr_icon = "mdi:air-filter"
    _attr_name = "Fresh air"

    def __init__(self, instance: dict[str, Any], ac_key: str) -> None:
        """Initialize an Advantage Air fresh air control."""
        super().__init__(instance, ac_key)
        self._attr_unique_id += "-freshair"

    @property
    def is_on(self) -> bool:
        """Return the fresh air status."""
        return self._ac["freshAirStatus"] == ADVANTAGE_AIR_STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn fresh air on."""
        await self.aircon(
            {self.ac_key: {"info": {"freshAirStatus": ADVANTAGE_AIR_STATE_ON}}}
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn fresh air off."""
        await self.aircon(
            {self.ac_key: {"info": {"freshAirStatus": ADVANTAGE_AIR_STATE_OFF}}}
        )
