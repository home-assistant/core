"""Component providing support for Reolink light entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import Host

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkChannelCoordinatorEntity


@dataclass
class ReolinkLightEntityDescriptionMixin:
    """Mixin values for Reolink light entities."""

    is_on_fn: Callable[[Host, int], bool]
    turn_on_off_fn: Callable[[Host, int, bool], Any]


@dataclass
class ReolinkLightEntityDescription(
    LightEntityDescription, ReolinkLightEntityDescriptionMixin
):
    """A class that describes light entities."""

    supported_fn: Callable[[Host, int], bool] = lambda api, ch: True
    get_brightness_fn: Callable[[Host, int], int] | None = None
    set_brightness_fn: Callable[[Host, int, float], Any] | None = None


LIGHT_ENTITIES = (
    ReolinkLightEntityDescription(
        key="floodlight",
        name="Floodlight",
        icon="mdi:spotlight-beam",
        supported_fn=lambda api, ch: api.supported(ch, "floodLight"),
        is_on_fn=lambda api, ch: api.whiteled_state(ch),
        turn_on_off_fn=lambda api, ch, value: api.set_whiteled(ch, state=value),
        get_brightness_fn=lambda api, ch: api.whiteled_brightness(ch),
        set_brightness_fn=lambda api, ch, value: api.set_whiteled(ch, brightness=value),
    ),
    ReolinkLightEntityDescription(
        key="ir_lights",
        name="Infra red lights in night mode",
        icon="mdi:led-off",
        entity_category=EntityCategory.CONFIG,
        supported_fn=lambda api, ch: api.supported(ch, "ir_lights"),
        is_on_fn=lambda api, ch: api.ir_enabled(ch),
        turn_on_off_fn=lambda api, ch, value: api.set_ir_lights(ch, value),
    ),
    ReolinkLightEntityDescription(
        key="status_led",
        name="Status LED",
        icon="mdi:lightning-bolt-circle",
        entity_category=EntityCategory.CONFIG,
        supported_fn=lambda api, ch: api.supported(ch, "power_led"),
        is_on_fn=lambda api, ch: api.status_led_enabled(ch),
        turn_on_off_fn=lambda api, ch, value: api.set_status_led(ch, value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink light entities."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        ReolinkLightEntity(reolink_data, channel, entity_description)
        for entity_description in LIGHT_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported_fn(reolink_data.host.api, channel)
    )


class ReolinkLightEntity(ReolinkChannelCoordinatorEntity, LightEntity):
    """Base light entity class for Reolink IP cameras."""

    entity_description: ReolinkLightEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkLightEntityDescription,
    ) -> None:
        """Initialize Reolink light entity."""
        super().__init__(reolink_data, channel)
        self.entity_description = entity_description

        self._attr_unique_id = (
            f"{self._host.unique_id}_{channel}_{entity_description.key}"
        )

        if entity_description.set_brightness_fn is None:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF
        else:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.entity_description.is_on_fn(self._host.api, self._channel)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0.255."""
        if self.entity_description.get_brightness_fn is None:
            return None

        return round(
            255
            * (
                self.entity_description.get_brightness_fn(self._host.api, self._channel)
                / 100.0
            )
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        await self.entity_description.turn_on_off_fn(
            self._host.api, self._channel, False
        )
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on."""
        if (
            brightness := kwargs.get(ATTR_BRIGHTNESS)
        ) is not None and self.entity_description.set_brightness_fn is not None:
            brightness_pct = int(brightness / 255.0 * 100)
            await self.entity_description.set_brightness_fn(
                self._host.api, self._channel, brightness_pct
            )

        await self.entity_description.turn_on_off_fn(
            self._host.api, self._channel, True
        )
        self.async_write_ha_state()
