"""Support for Velbus light."""
from __future__ import annotations

from typing import Any

from velbusaio.channels import (
    Button as VelbusButton,
    Channel as VelbusChannel,
    Dimmer as VelbusDimmer,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_FLASH,
    ATTR_TRANSITION,
    FLASH_LONG,
    FLASH_SHORT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import VelbusEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    entities: list[Entity] = []
    for channel in cntrl.get_all("light"):
        entities.append(VelbusLight(channel))
    for channel in cntrl.get_all("led"):
        entities.append(VelbusButtonLight(channel))
    async_add_entities(entities)


class VelbusLight(VelbusEntity, LightEntity):
    """Representation of a Velbus light."""

    _channel: VelbusDimmer
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_supported_features = LightEntityFeature.TRANSITION

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        return self._channel.is_on()

    @property
    def brightness(self) -> int:
        """Return the brightness of the light."""
        return int((self._channel.get_dimmer_state() * 255) / 100)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the Velbus light to turn on."""
        if ATTR_BRIGHTNESS in kwargs:
            # Make sure a low but non-zero value is not rounded down to zero
            if kwargs[ATTR_BRIGHTNESS] == 0:
                brightness = 0
            else:
                brightness = max(int((kwargs[ATTR_BRIGHTNESS] * 100) / 255), 1)
            attr, *args = (
                "set_dimmer_state",
                brightness,
                kwargs.get(ATTR_TRANSITION, 0),
            )
        else:
            attr, *args = (
                "restore_dimmer_state",
                kwargs.get(ATTR_TRANSITION, 0),
            )
        await getattr(self._channel, attr)(*args)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the velbus light to turn off."""
        attr, *args = (
            "set_dimmer_state",
            0,
            kwargs.get(ATTR_TRANSITION, 0),
        )
        await getattr(self._channel, attr)(*args)


class VelbusButtonLight(VelbusEntity, LightEntity):
    """Representation of a Velbus light."""

    _channel: VelbusButton
    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_supported_features = LightEntityFeature.FLASH

    def __init__(self, channel: VelbusChannel) -> None:
        """Initialize the button light (led)."""
        super().__init__(channel)
        self._attr_name = f"LED {self._channel.get_name()}"

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        return self._channel.is_on()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the Velbus light to turn on."""
        if ATTR_FLASH in kwargs:
            if kwargs[ATTR_FLASH] == FLASH_LONG:
                attr, *args = "set_led_state", "slow"
            elif kwargs[ATTR_FLASH] == FLASH_SHORT:
                attr, *args = "set_led_state", "fast"
            else:
                attr, *args = "set_led_state", "on"
        else:
            attr, *args = "set_led_state", "on"
        await getattr(self._channel, attr)(*args)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the velbus light to turn off."""
        attr, *args = "set_led_state", "off"
        await getattr(self._channel, attr)(*args)
