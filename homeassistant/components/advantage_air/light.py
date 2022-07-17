"""Light platform for Advantage Air integration."""
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ADVANTAGE_AIR_LIGHTS,
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
    """Set up AdvantageAir light platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities = []
    if ADVANTAGE_AIR_LIGHTS in instance["coordinator"].data:
        for light in instance["coordinator"].data[ADVANTAGE_AIR_LIGHTS]["lights"]:
            if light.get("relay"):
                entities.append(AdvantageAirLight(instance, light))
            else:
                entities.append(AdvantageAirLightDimmable(instance, light))
    async_add_entities(entities)


class AdvantageAirLight(AdvantageAirEntity, LightEntity):
    """Representation of Advantage Air Light."""

    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, instance, light):
        """Initialize an Advantage Air Light."""
        super().__init__(instance)
        self.async_set_light = instance["async_set_light"]
        self._id = light["id"]
        self._attr_unique_id = f'{self.coordinator.data["system"]["rid"]}-{self._id}'

    @property
    def _light(self):
        """Return the light object."""
        return self.coordinator.data[ADVANTAGE_AIR_LIGHTS]["lights"][self._id]

    @property
    def name(self) -> str:
        """Return a name for this light entity."""
        return self._light["name"]

    @property
    def is_on(self) -> bool:
        """Return if the light is on."""
        return self._light["state"] == ADVANTAGE_AIR_STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self.async_set_light({"id": self._id, "state": ADVANTAGE_AIR_STATE_ON})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.async_set_light({"id": self._id, "state": ADVANTAGE_AIR_STATE_OFF})


class AdvantageAirLightDimmable(AdvantageAirLight):
    """Representation of Advantage Air Dimmable Light."""

    _attr_supported_color_modes = {ColorMode.ONOFF, ColorMode.BRIGHTNESS}

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return round(self._light["value"] * 255 / 100)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on and optionally set the brightness."""
        data = {"id": self._id, "state": ADVANTAGE_AIR_STATE_ON}
        if ATTR_BRIGHTNESS in kwargs:
            data["value"] = round(kwargs[ATTR_BRIGHTNESS] / 255)
        await self.async_set_light(data)
