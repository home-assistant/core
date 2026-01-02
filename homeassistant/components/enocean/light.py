"""Support for EnOcean light sources."""

from __future__ import annotations

from typing import Any

from homeassistant_enocean.entity_id import EnOceanEntityID
from homeassistant_enocean.gateway import EnOceanHomeAssistantGateway

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_entry import EnOceanConfigEntry
from .entity import EnOceanEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway = config_entry.runtime_data.gateway

    for entity_id in gateway.light_entities:
        async_add_entities([EnOceanLight(entity_id, gateway=gateway)])


class EnOceanLight(EnOceanEntity, LightEntity):
    """Representation of EnOcean lights."""

    def __init__(
        self,
        entity_id: EnOceanEntityID,
        gateway: EnOceanHomeAssistantGateway,
    ) -> None:
        """Initialize the EnOcean light."""
        super().__init__(enocean_entity_id=entity_id, gateway=gateway)
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_brightness: int | None = None
        self._attr_is_on: bool | None = None
        self.gateway.register_light_callback(self.enocean_entity_id, self.update)

    def update(
        self, is_on: bool, brightness: int | None, color_temp_kelvin: int | None
    ) -> None:
        """Update the light state."""
        self._attr_is_on = is_on
        self._attr_brightness = brightness
        self._attr_color_temp_kelvin = color_temp_kelvin
        self.schedule_update_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light source on or sets a specific dimmer value."""

        # set new brightness if a value is given
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            self._attr_brightness = brightness

        # if no brightness is set, assume full brightness
        if self._attr_brightness is None:
            self._attr_brightness = 255

        # turn on the light with the given brightness and update state
        self.gateway.light_turn_on(self.enocean_entity_id, self._attr_brightness)
        self._attr_is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        self.gateway.light_turn_off(self.enocean_entity_id)
        self._attr_is_on = False
        self.schedule_update_ha_state()

    @property
    def brightness(self) -> int | None:
        """Brightness of the light."""
        return self._attr_brightness

    @property
    def is_on(self) -> bool | None:
        """If light is on."""
        return self._attr_is_on
