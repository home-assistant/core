"""Support for TPLink number entities."""

from __future__ import annotations

import logging

from kasa import Device, Feature

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import (
    CoordinatedTPLinkEntity,
    _description_for_feature,
    _entities_for_device_and_its_children,
    async_refresh_after,
)
from .models import TPLinkData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    entities = _entities_for_device_and_its_children(
        device,
        feature_type=Feature.Number,
        entity_class=Number,
        coordinator=parent_coordinator,
    )

    async_add_entities(entities)


class Number(CoordinatedTPLinkEntity, NumberEntity):
    """Representation of a feature-based TPLink sensor."""

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        feature: Feature,
        parent: Device | None = None,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(device, coordinator, feature=feature, parent=parent)
        self._feature: Feature
        self.entity_description = _description_for_feature(
            NumberEntityDescription,
            feature,
            native_min_value=feature.minimum_value,
            native_max_value=feature.maximum_value,
        )

    @async_refresh_after
    async def async_set_native_value(self, value: float) -> None:
        """Set feature value."""
        await self._feature.set_value(int(value))  # type: ignore[no-untyped-call]

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_native_value = self._feature.value
