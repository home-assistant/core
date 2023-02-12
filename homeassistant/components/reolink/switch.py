"""This component provides support for Reolink switch entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import Host

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkCoordinatorEntity


@dataclass
class ReolinkSwitchEntityDescriptionMixin:
    """Mixin values for Reolink switch entities."""

    value: Callable[[Host, int | None], bool]
    method: Callable[[Host, int | None, bool], Any]


@dataclass
class ReolinkSwitchEntityDescription(
    SwitchEntityDescription, ReolinkSwitchEntityDescriptionMixin
):
    """A class that describes switch entities."""

    supported: Callable[[Host, int | None], bool] = lambda api, ch: True


SWITCH_ENTITIES = (
    ReolinkSwitchEntityDescription(
        key="floodlight",
        name="Floodlight",
        icon="mdi:spotlight-beam",
        supported=lambda api, ch: api.supported(ch, "floodLight"),
        value=lambda api, ch: api.whiteled_state(ch),
        method=lambda api, ch, value: api.set_whiteled(ch, state=value),
    ),
    ReolinkSwitchEntityDescription(
        key="ir_lights",
        name="Infra red lights",
        icon="mdi:led-off",
        supported=lambda api, ch: api.supported(ch, "ir_lights"),
        value=lambda api, ch: api.ir_enabled(ch),
        method=lambda api, ch, value: api.set_ir_lights(ch, value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink switch entities."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        ReolinkSwitchEntity(reolink_data, channel, entity_description)
        for entity_description in SWITCH_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    )


class ReolinkSwitchEntity(ReolinkCoordinatorEntity, SwitchEntity):
    """Base switch entity class for Reolink IP cameras."""

    _attr_has_entity_name = True
    entity_description: ReolinkSwitchEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkSwitchEntityDescription,
    ) -> None:
        """Initialize Reolink switch entity."""
        super().__init__(reolink_data, channel)
        self.entity_description = entity_description

        self._attr_unique_id = (
            f"{self._host.unique_id}_{self._channel}_{entity_description.key}"
        )

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.entity_description.value(self._host.api, self._channel)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.entity_description.method(self._host.api, self._channel, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.entity_description.method(self._host.api, self._channel, False)
        await self.coordinator.async_request_refresh()
