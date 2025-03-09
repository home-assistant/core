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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VelbusConfigEntry
from .entity import VelbusEntity, api_call

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    await entry.runtime_data.scan_task
    entities: list[Entity] = [
        VelbusLight(channel)
        for channel in entry.runtime_data.controller.get_all_light()
    ]
    entities.extend(
        VelbusButtonLight(channel)
        for channel in entry.runtime_data.controller.get_all_led()
    )
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

    @api_call
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

    @api_call
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

    @api_call
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the Velbus light to turn on."""
        if (flash := ATTR_FLASH in kwargs) and kwargs[ATTR_FLASH] == FLASH_LONG:
            await self._channel.set_led_state("slow")
        elif flash and kwargs[ATTR_FLASH] == FLASH_SHORT:
            await self._channel.set_led_state("fast")
        else:
            await self._channel.set_led_state("on")

    @api_call
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the velbus light to turn off."""
        await self._channel.set_led_state("off")
