"""Support for TPLink number entities."""

from __future__ import annotations

import logging
from typing import cast

from kasa import Feature, SmartDevice, SmartPlug

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import (
    CoordinatedTPLinkEntity,
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
    device = cast(SmartPlug, parent_coordinator.device)

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
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
        feature: Feature,
        parent: SmartDevice = None,
    ):
        """Initialize the number entity."""
        super().__init__(device, coordinator, feature=feature, parent=parent)
        # TODO: generalize creation of entitydescription into CoordinatedTPLinkEntity?
        self.entity_description = NumberEntityDescription(
            key=feature.id,
            translation_key=feature.id,
            name=feature.name,
            icon=feature.icon,
            native_min_value=feature.minimum_value,
            native_max_value=feature.maximum_value,
            entity_registry_enabled_default=feature.category
            is not Feature.Category.Debug,
        )

    @async_refresh_after
    async def async_set_native_value(self, value: float) -> None:
        """Set feature value."""
        await self._feature.set_value(int(value))

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_native_value = self._feature.value
