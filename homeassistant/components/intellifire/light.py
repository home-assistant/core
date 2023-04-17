"""The IntelliFire Light."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from intellifire4py import IntellifireControlAsync, IntellifirePollData

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IntellifireDataUpdateCoordinator
from .entity import IntellifireEntity


@dataclass
class IntellifireLightRequiredKeysMixin:
    """Required keys for fan entity."""

    set_fn: Callable[[IntellifireControlAsync, int], Awaitable]
    value_fn: Callable[[IntellifirePollData], bool]


@dataclass
class IntellifireLightEntityDescription(
    LightEntityDescription, IntellifireLightRequiredKeysMixin
):
    """Describes a light entity."""


INTELLIFIRE_LIGHTS: tuple[IntellifireLightEntityDescription, ...] = (
    IntellifireLightEntityDescription(
        key="lights",
        name="Lights",
        has_entity_name=True,
        set_fn=lambda control_api, level: control_api.set_lights(level=level),
        value_fn=lambda data: data.light_level,
    ),
)


class IntellifireLight(IntellifireEntity, LightEntity):
    """This is a Light entity for the fireplace."""

    entity_description: IntellifireLightEntityDescription
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def brightness(self):
        """Return the current brightness 0-255."""
        return 85 * self.entity_description.value_fn(self.coordinator.read_api.data)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.entity_description.value_fn(self.coordinator.read_api.data) >= 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if ATTR_BRIGHTNESS in kwargs:
            light_level = int(kwargs[ATTR_BRIGHTNESS] / 85)
        else:
            light_level = 2

        await self.entity_description.set_fn(self.coordinator.control_api, light_level)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self.entity_description.set_fn(self.coordinator.control_api, 0)
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fans."""
    coordinator: IntellifireDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if coordinator.data.has_light:
        async_add_entities(
            IntellifireLight(coordinator=coordinator, description=description)
            for description in INTELLIFIRE_LIGHTS
        )
        return
