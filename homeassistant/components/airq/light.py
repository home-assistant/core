"""Definition of air-Q light platform (realised via AirQ LEDs)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from aioairq import AirQ

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import brightness_to_value, value_to_brightness

from . import AirQConfigEntry, AirQCoordinator

LED_VALUE_SCALE = (1.0, 10.0)  # must not include 0 as 0 == off
LED_VALUE_DEFAULT = 6.0
BRIGHTNESS_DEFAULT = 153  # ~60%

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AirQLightEntityDescription(LightEntityDescription):
    """Describes AirQ LED entity."""

    value: Callable[[dict], float]


AIRQ_LIGHT_DESCRIPTION = AirQLightEntityDescription(
    key="airq_leds",
    translation_key="airq_leds",
    value=lambda device: device.get("brightness", LED_VALUE_DEFAULT),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities based on a config entry."""

    coordinator = entry.runtime_data
    entities = [AirQLight(coordinator, AIRQ_LIGHT_DESCRIPTION)]

    async_add_entities(entities)


class AirQLight(CoordinatorEntity, LightEntity):
    """Representation of the LEDs from a single AirQ."""

    _attr_has_entity_name = True
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(
        self,
        coordinator: AirQCoordinator,
        description: AirQLightEntityDescription,
    ) -> None:
        """Initialize a single sensor."""
        super().__init__(coordinator)
        self.entity_description: AirQLightEntityDescription = description

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._update_attr()

    def _update_attr(self) -> None:
        led_value = self.entity_description.value(self.coordinator.data)
        self._attr_is_on = bool(led_value)
        if self._attr_is_on:
            # do not update if off, to be able to restore the brightness once toggled on
            self._attr_brightness = value_to_brightness(LED_VALUE_SCALE, led_value)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle the LED value received from the coordinator."""
        self._update_attr()
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        # if HA changes brightness, ATTR_BRIGHTNESS is in kwargs.
        # otherwise restore to cached brightness or fall back to the default
        brightness = (
            kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness) or BRIGHTNESS_DEFAULT
        )
        self._attr_brightness = brightness
        self._attr_is_on = True

        led_value = brightness_to_value(LED_VALUE_SCALE, brightness)
        _LOGGER.debug("Switching LED to value of %f", led_value)
        await self._device.set_current_brightness(led_value)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        self._attr_is_on = False
        await self._device.set_current_brightness(0)
        self.async_write_ha_state()

    @property
    def _device(self) -> AirQ:
        """Return the device."""
        # the following assertion pacifies mypy
        assert isinstance(self.coordinator, AirQCoordinator)
        return self.coordinator.airq
