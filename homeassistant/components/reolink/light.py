"""Component providing support for Reolink light entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import Host
from reolink_aio.exceptions import InvalidParameterError, ReolinkError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkChannelCoordinatorEntity, ReolinkChannelEntityDescription


@dataclass(frozen=True, kw_only=True)
class ReolinkLightEntityDescription(
    LightEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes light entities."""

    get_brightness_fn: Callable[[Host, int], int | None] | None = None
    is_on_fn: Callable[[Host, int], bool]
    set_brightness_fn: Callable[[Host, int, int], Any] | None = None
    turn_on_off_fn: Callable[[Host, int, bool], Any]


LIGHT_ENTITIES = (
    ReolinkLightEntityDescription(
        key="floodlight",
        cmd_key="GetWhiteLed",
        translation_key="floodlight",
        supported=lambda api, ch: api.supported(ch, "floodLight"),
        is_on_fn=lambda api, ch: api.whiteled_state(ch),
        turn_on_off_fn=lambda api, ch, value: api.set_whiteled(ch, state=value),
        get_brightness_fn=lambda api, ch: api.whiteled_brightness(ch),
        set_brightness_fn=lambda api, ch, value: api.set_whiteled(ch, brightness=value),
    ),
    ReolinkLightEntityDescription(
        key="status_led",
        cmd_key="GetPowerLed",
        translation_key="status_led",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api, ch: api.supported(ch, "power_led"),
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
        if entity_description.supported(reolink_data.host.api, channel)
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
        self.entity_description = entity_description
        super().__init__(reolink_data, channel)

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

        bright_pct = self.entity_description.get_brightness_fn(
            self._host.api, self._channel
        )
        if bright_pct is None:
            return None

        return round(255 * bright_pct / 100.0)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        try:
            await self.entity_description.turn_on_off_fn(
                self._host.api, self._channel, False
            )
        except ReolinkError as err:
            raise HomeAssistantError(err) from err
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on."""
        if (
            brightness := kwargs.get(ATTR_BRIGHTNESS)
        ) is not None and self.entity_description.set_brightness_fn is not None:
            brightness_pct = int(brightness / 255.0 * 100)
            try:
                await self.entity_description.set_brightness_fn(
                    self._host.api, self._channel, brightness_pct
                )
            except InvalidParameterError as err:
                raise ServiceValidationError(err) from err
            except ReolinkError as err:
                raise HomeAssistantError(err) from err

        try:
            await self.entity_description.turn_on_off_fn(
                self._host.api, self._channel, True
            )
        except ReolinkError as err:
            raise HomeAssistantError(err) from err
        self.async_write_ha_state()
