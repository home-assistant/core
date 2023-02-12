"""This component provides support for Reolink select entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reolink_aio.api import Host, SpotlightModeEnum

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkCoordinatorEntity


@dataclass
class ReolinkSelectEntityDescriptionMixin:
    """Mixin values for Reolink select entities."""

    value: Callable[[Host, int | None], str]
    method: Callable[[Host, int | None, str], Any]


@dataclass
class ReolinkSelectEntityDescription(
    SelectEntityDescription, ReolinkSelectEntityDescriptionMixin
):
    """A class that describes select entities."""

    supported: Callable[[Host, int | None], bool] = lambda api, ch: True


SELECT_ENTITIES = (
    ReolinkSelectEntityDescription(
        key="floodlight mode",
        name="Floodlight mode",
        icon="mdi:spotlight-beam",
        options=[mode.name for mode in SpotlightModeEnum],
        supported=lambda api, ch: api.supported(ch, "floodLight"),
        value=lambda api, ch: SpotlightModeEnum(api.whiteled_mode(ch)).name,
        method=lambda api, ch, value: api.set_whiteled(ch, mode=value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink select entities."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        ReolinkSelectEntity(reolink_data, channel, entity_description)
        for entity_description in SELECT_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    )


class ReolinkSelectEntity(ReolinkCoordinatorEntity, SelectEntity):
    """Base select entity class for Reolink IP cameras."""

    _attr_has_entity_name = True
    entity_description: ReolinkSelectEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkSelectEntityDescription,
    ) -> None:
        """Initialize Reolink select entity."""
        super().__init__(reolink_data, channel)
        self.entity_description = entity_description

        self._attr_unique_id = (
            f"{self._host.unique_id}_{self._channel}_{entity_description.key}"
        )

    @property
    def current_option(self) -> str:
        """The current select option."""
        return self.entity_description.value(self._host.api, self._channel)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.method(self._host.api, self._channel, option)
