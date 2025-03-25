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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import (
    ReolinkChannelCoordinatorEntity,
    ReolinkChannelEntityDescription,
    ReolinkHostCoordinatorEntity,
    ReolinkHostEntityDescription,
)
from .util import ReolinkConfigEntry, ReolinkData, raise_translated_error

PARALLEL_UPDATES = 0


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


@dataclass(frozen=True, kw_only=True)
class ReolinkHostLightEntityDescription(
    LightEntityDescription,
    ReolinkHostEntityDescription,
):
    """A class that describes host light entities."""

    is_on_fn: Callable[[Host], bool]
    turn_on_off_fn: Callable[[Host, bool], Any]


LIGHT_ENTITIES = (
    ReolinkLightEntityDescription(
        key="floodlight",
        cmd_key="GetWhiteLed",
        cmd_id=291,
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

HOST_LIGHT_ENTITIES = (
    ReolinkHostLightEntityDescription(
        key="hub_status_led",
        cmd_key="GetStateLight",
        translation_key="status_led",
        entity_category=EntityCategory.CONFIG,
        supported=lambda api: api.supported(None, "state_light"),
        is_on_fn=lambda api: api.state_light,
        turn_on_off_fn=lambda api, value: api.set_state_light(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ReolinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Reolink light entities."""
    reolink_data: ReolinkData = config_entry.runtime_data

    entities: list[ReolinkLightEntity | ReolinkHostLightEntity] = [
        ReolinkLightEntity(reolink_data, channel, entity_description)
        for entity_description in LIGHT_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    ]
    entities.extend(
        ReolinkHostLightEntity(reolink_data, entity_description)
        for entity_description in HOST_LIGHT_ENTITIES
        if entity_description.supported(reolink_data.host.api)
    )

    async_add_entities(entities)


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
        assert self.entity_description.get_brightness_fn is not None

        bright_pct = self.entity_description.get_brightness_fn(
            self._host.api, self._channel
        )
        if bright_pct is None:
            return None

        return round(255 * bright_pct / 100.0)

    @raise_translated_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        await self.entity_description.turn_on_off_fn(
            self._host.api, self._channel, False
        )
        self.async_write_ha_state()

    @raise_translated_error
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


class ReolinkHostLightEntity(ReolinkHostCoordinatorEntity, LightEntity):
    """Base host light entity class for Reolink IP cameras."""

    entity_description: ReolinkHostLightEntityDescription
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(
        self,
        reolink_data: ReolinkData,
        entity_description: ReolinkHostLightEntityDescription,
    ) -> None:
        """Initialize Reolink host light entity."""
        self.entity_description = entity_description
        super().__init__(reolink_data)

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.entity_description.is_on_fn(self._host.api)

    @raise_translated_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        await self.entity_description.turn_on_off_fn(self._host.api, False)
        self.async_write_ha_state()

    @raise_translated_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on."""
        await self.entity_description.turn_on_off_fn(self._host.api, True)
        self.async_write_ha_state()
