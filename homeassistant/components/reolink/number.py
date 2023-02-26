"""This component provides support for Reolink number entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import Host

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkCoordinatorEntity


@dataclass
class ReolinkNumberEntityDescriptionMixin:
    """Mixin values for Reolink number entities."""

    value: Callable[[Host, int | None], bool]
    get_min_value: Callable[[Host, int | None], float]
    get_max_value: Callable[[Host, int | None], float]
    method: Callable[[Host, int | None, float], Any]


@dataclass
class ReolinkNumberEntityDescription(
    NumberEntityDescription, ReolinkNumberEntityDescriptionMixin
):
    """A class that describes number entities."""

    mode: NumberMode = NumberMode.AUTO
    supported: Callable[[Host, int | None], bool] = lambda api, ch: True


NUMBER_ENTITIES = (
    ReolinkNumberEntityDescription(
        key="zoom",
        name="Zoom",
        icon="mdi:magnify",
        mode=NumberMode.SLIDER,
        native_step=1,
        get_min_value=lambda api, ch: api.zoom_range(ch)["zoom"]["pos"]["min"],
        get_max_value=lambda api, ch: api.zoom_range(ch)["zoom"]["pos"]["max"],
        supported=lambda api, ch: api.zoom_supported(ch),
        value=lambda api, ch: api.get_zoom(ch),
        method=lambda api, ch, value: api.set_zoom(ch, int(value)),
    ),
    ReolinkNumberEntityDescription(
        key="focus",
        name="Focus",
        icon="mdi:focus-field",
        mode=NumberMode.SLIDER,
        native_step=1,
        get_min_value=lambda api, ch: api.zoom_range(ch)["focus"]["pos"]["min"],
        get_max_value=lambda api, ch: api.zoom_range(ch)["focus"]["pos"]["max"],
        supported=lambda api, ch: api.zoom_supported(ch),
        value=lambda api, ch: api.get_focus(ch),
        method=lambda api, ch, value: api.set_zoom(ch, int(value)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink number entities."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        ReolinkNumberEntity(reolink_data, channel, entity_description)
        for entity_description in NUMBER_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    )


class ReolinkNumberEntity(ReolinkCoordinatorEntity, NumberEntity):
    """Base number entity class for Reolink IP cameras."""

    entity_description: ReolinkNumberEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkNumberEntityDescription,
    ) -> None:
        """Initialize Reolink number entity."""
        super().__init__(reolink_data, channel)
        self.entity_description = entity_description

        self._attr_native_min_value = self.entity_description.get_min_value(
            self._host.api, self._channel
        )
        self._attr_native_max_value = self.entity_description.get_max_value(
            self._host.api, self._channel
        )
        self._attr_mode = entity_description.mode
        self._attr_unique_id = (
            f"{self._host.unique_id}_{self._channel}_{entity_description.key}"
        )

    @property
    def native_value(self) -> float:
        """State of the number entity."""
        return self.entity_description.value(self._host.api, self._channel)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.entity_description.method(self._host.api, self._channel, value)
