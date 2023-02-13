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

    @property
    def native_value(self) -> float:
        """State of the light entity."""
        return self.entity_description.value(self._host.api, self._channel)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.entity_description.method(self._host.api, self._channel, value)
        self.async_write_ha_state()
