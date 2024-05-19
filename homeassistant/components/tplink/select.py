"""Support for TPLink select entities."""

from __future__ import annotations

from kasa import Device, Feature

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import (
    CoordinatedTPLinkEntity,
    _description_for_feature,
    _entities_for_device_and_its_children,
    async_refresh_after,
)
from .models import TPLinkData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up selects."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    entities = _entities_for_device_and_its_children(
        device,
        feature_type=Feature.Choice,
        entity_class=Select,
        coordinator=parent_coordinator,
    )

    async_add_entities(entities)


class Select(CoordinatedTPLinkEntity, SelectEntity):
    """Representation of a tplink select entity."""

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        feature: Feature,
        parent: Device | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, coordinator, feature=feature, parent=parent)
        self._feature: Feature
        self.entity_description = _description_for_feature(
            SelectEntityDescription, feature, options=feature.choices
        )
        self._async_update_attrs()

    @async_refresh_after
    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        await self._feature.set_value(option)

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_current_option = self._feature.value
