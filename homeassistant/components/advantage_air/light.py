"""Light platform for Advantage Air integration."""
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ADVANTAGE_AIR_STATE_ON, DOMAIN as ADVANTAGE_AIR_DOMAIN
from .entity import AdvantageAirEntity, AdvantageAirThingEntity
from .models import AdvantageAirData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir light platform."""

    instance: AdvantageAirData = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities: list[LightEntity] = []
    if my_lights := instance.coordinator.data.get("myLights"):
        for light in my_lights["lights"].values():
            if light.get("relay"):
                entities.append(AdvantageAirLight(instance, light))
            else:
                entities.append(AdvantageAirLightDimmable(instance, light))
    if things := instance.coordinator.data.get("myThings"):
        for thing in things["things"].values():
            if thing["channelDipState"] == 4:  # 4 = "Light (on/off)""
                entities.append(AdvantageAirThingLight(instance, thing))
            elif thing["channelDipState"] == 5:  # 5 = "Light (Dimmable)""
                entities.append(AdvantageAirThingLightDimmable(instance, thing))
    async_add_entities(entities)


class AdvantageAirLight(AdvantageAirEntity, LightEntity):
    """Representation of Advantage Air Light."""

    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, instance: AdvantageAirData, light: dict[str, Any]) -> None:
        """Initialize an Advantage Air Light."""
        super().__init__(instance)

        self._id: str = light["id"]
        self._attr_unique_id += f"-{self._id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(ADVANTAGE_AIR_DOMAIN, self._attr_unique_id)},
            via_device=(ADVANTAGE_AIR_DOMAIN, self.coordinator.data["system"]["rid"]),
            manufacturer="Advantage Air",
            model=light.get("moduleType"),
            name=light["name"],
        )
        self.async_update_state = self.update_handle_factory(
            instance.api.lights.async_update_state, self._id
        )

    @property
    def _data(self) -> dict[str, Any]:
        """Return the light object."""
        return self.coordinator.data["myLights"]["lights"][self._id]

    @property
    def is_on(self) -> bool:
        """Return if the light is on."""
        return self._data["state"] == ADVANTAGE_AIR_STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self.async_update_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.async_update_state(False)


class AdvantageAirLightDimmable(AdvantageAirLight):
    """Representation of Advantage Air Dimmable Light."""

    _attr_supported_color_modes = {ColorMode.ONOFF, ColorMode.BRIGHTNESS}

    def __init__(self, instance: AdvantageAirData, light: dict[str, Any]) -> None:
        """Initialize an Advantage Air Dimmable Light."""
        super().__init__(instance, light)
        self.async_update_value = self.update_handle_factory(
            instance.api.lights.async_update_value, self._id
        )

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return round(self._data["value"] * 255 / 100)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on and optionally set the brightness."""
        if ATTR_BRIGHTNESS in kwargs:
            return await self.async_update_value(round(kwargs[ATTR_BRIGHTNESS] / 2.55))
        return await self.async_update_state(True)


class AdvantageAirThingLight(AdvantageAirThingEntity, LightEntity):
    """Representation of Advantage Air Light controlled by myThings."""

    _attr_supported_color_modes = {ColorMode.ONOFF}


class AdvantageAirThingLightDimmable(AdvantageAirThingEntity, LightEntity):
    """Representation of Advantage Air Dimmable Light controlled by myThings."""

    _attr_supported_color_modes = {ColorMode.ONOFF, ColorMode.BRIGHTNESS}

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return round(self._data["value"] * 255 / 100)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on by setting the brightness."""
        await self.async_update_value(round(kwargs.get(ATTR_BRIGHTNESS, 255) / 2.55))
