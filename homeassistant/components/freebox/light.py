"""Support for the LED Strip in the Freebox Ultra Limited Edition."""

from __future__ import annotations

import logging
from math import ceil
from typing import Any

from freebox_api.exceptions import InsufficientPermissionsError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    EFFECT_OFF,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .router import FreeboxConfigEntry, FreeboxRouter

_LOGGER = logging.getLogger(__name__)


LED_STRIP_DESCRIPTION = LightEntityDescription(
    key="led_strip",
    name="Freebox LED Strip",
    entity_category=EntityCategory.CONFIG,
)

LED_STRIP_BRIGHTNESS_SCALE = (1, 100)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreeboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch."""
    router = entry.runtime_data
    lcd_config = await router.lcd.get_configuration()
    # Only provide the LED Strip entity on supported models (currently, only Freebox Ultra Limited Edition)
    if "led_strip_enabled" in lcd_config:
        entities: list[LightEntity] = [FreeboxLEDStrip(router, LED_STRIP_DESCRIPTION)]
        async_add_entities(entities, True)


class FreeboxLEDStrip(LightEntity):
    """Representation of a freebox LED Strip."""

    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(
        self, router: FreeboxRouter, entity_description: LightEntityDescription
    ) -> None:
        """Initialize the light."""
        self.entity_description = entity_description
        self._router = router
        self._attr_device_info = router.device_info
        self._attr_unique_id = f"{router.mac} {entity_description.name}"
        self._is_on: bool = False
        self._native_brightness: int = 100
        self._effect: str = EFFECT_OFF
        self._effect_list: list[str] = []

    @property
    def is_on(self) -> bool:
        """LED Strip on/off."""
        return self._is_on

    @property
    def brightness(self) -> int:
        """LED Strip brightness, mapped to 1..255 from Freebox's 1..100 range."""
        return value_to_brightness(LED_STRIP_BRIGHTNESS_SCALE, self._native_brightness)

    @property
    def effect(self) -> str:
        """LED Strip animation."""
        return self._effect if self._is_on else EFFECT_OFF

    @property
    def effect_list(self) -> list[str]:
        """LED Strip supported animations."""
        return self._effect_list

    @property
    def color_mode(self) -> ColorMode:
        """LED Strip color mode."""
        return ColorMode.BRIGHTNESS

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """LED Strip supported colors modes."""
        return {ColorMode.BRIGHTNESS}

    async def _async_set_value(
        self, enabled: bool, brightness: int | None = None, effect: str | None = None
    ) -> None:
        """Turn the LED Strip on or off."""
        try:
            config: dict[str, Any] = {"led_strip_enabled": enabled}
            if brightness is not None:
                config["led_strip_brightness"] = brightness
            if effect is not None:
                config["led_strip_animation"] = effect
            await self._router.lcd.set_configuration(config)
        except InsufficientPermissionsError:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox"
                " settings. Please refer to documentation"
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the LED Strip on."""
        native_brightness = (
            ceil(
                brightness_to_value(LED_STRIP_BRIGHTNESS_SCALE, kwargs[ATTR_BRIGHTNESS])
            )
            if ATTR_BRIGHTNESS in kwargs
            else None
        )
        effect = kwargs.get(ATTR_EFFECT)
        await self._async_set_value(True, brightness=native_brightness, effect=effect)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the LED Strip off."""
        await self._async_set_value(False)

    async def async_update(self) -> None:
        """Update LED Strip state from the API."""
        data = await self._router.lcd.get_configuration()
        self._is_on = bool(data["led_strip_enabled"])
        self._native_brightness = int(data["led_strip_brightness"])
        self._effect = str(data["led_strip_animation"])
        self._effect_list = list[str](data["available_led_strip_animations"])
