"""This component provides support for Reolink light entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import Host

from homeassistant.components.light import LightEntity, LightEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkCoordinatorEntity


@dataclass
class ReolinkLightEntityDescriptionMixin:
    """Mixin values for Reolink light entities."""

    is_on: Callable[[Host, int | None], bool]
    turn_on_off: Callable[[Host, int | None, bool], Any]


@dataclass
class ReolinkLightEntityDescription(
    LightEntityDescription, ReolinkLightEntityDescriptionMixin
):
    """A class that describes light entities."""

    supported: Callable[[Host, int | None], bool] = lambda api, ch: True
    get_brightness: Callable[[Host, int | None], float] | None = None
    set_brightness: Callable[[Host, int | None, float], Any] | None = None


LIGHT_ENTITIES = (
    ReolinkLightEntityDescription(
        key="floodlight",
        name="Floodlight",
        icon="mdi:spotlight-beam",
        supported=lambda api, ch: api.supported(ch, "floodLight"),
        is_on=lambda api, ch: api.whiteled_state(ch),
        turn_on_off=lambda api, ch, value: api.set_whiteled(ch, state=value),
        get_brightness=lambda api, ch: api.whiteled_brightness(ch),
        set_brightness=lambda api, ch, value: api.set_whiteled(ch, brightness=int(value)),
    ),
    ReolinkLightEntityDescription(
        key="ir_lights",
        name="Infra red lights in night mode",
        icon="mdi:led-off",
        supported=lambda api, ch: api.supported(ch, "ir_lights"),
        is_on=lambda api, ch: api.ir_enabled(ch),
        turn_on_off=lambda api, ch, value: api.set_ir_lights(ch, value),
    ),
    ReolinkLightEntityDescription(
        key="status_led",
        name="Status led",
        icon="mdi:lightning-bolt-circle",
        supported=lambda api, ch: api.supported(ch, "status_led"),
        is_on=lambda api, ch: api.status_led_enabled(ch),
        turn_on_off=lambda api, ch, value: api.set_status_led(ch, value),
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
        if entity_description.supported(reolink_data.host.api, channel)
    )


class ReolinkLightEntity(ReolinkCoordinatorEntity, LightEntity):
    """Base light entity class for Reolink IP cameras."""

    _attr_has_entity_name = True
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
            f"{self._host.unique_id}_{self._channel}_{entity_description.key}"
        )

        if self.entity_description.set_brightness is None:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF
        else:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.entity_description.is_on(self._host.api, self._channel)

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0.255."""
        if self.entity_description.get_brightness is None:
            return None

        return round(255 * (self.entity_description.get_brightness(self._host.api, self._channel) / 100))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        await self.entity_description.turn_on_off(self._host.api, self._channel, False)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None and self.entity_description.set_brightness is not None:
            await self.entity_description.set_brightness(self._host.api, self._channel, brightness)

        await self.entity_description.turn_on_off(self._host.api, self._channel, True)
        self.async_write_ha_state()
