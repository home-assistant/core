"""Support for TPLink switch entities."""

from __future__ import annotations

import logging
from typing import Any

from kasa import Device, Feature

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
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
    """Set up switches."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    entities = _entities_for_device_and_its_children(
        device,
        feature_type=Feature.Switch,
        entity_class=Switch,
        coordinator=parent_coordinator,
    )

    async_add_entities(entities, update_before_add=True)


class Switch(CoordinatedTPLinkEntity, SwitchEntity):
    """Representation of a feature-based TPLink sensor."""

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        feature: Feature,
        parent: Device | None = None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(device, coordinator, feature=feature, parent=parent)
        self._feature: Feature

        # Use the device name for the primary switch control
        if feature.category is Feature.Category.Primary:
            self._attr_name = None

        self.entity_description = _description_for_feature(
            SwitchEntityDescription, feature
        )

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._feature.set_value(True)  # type: ignore[no-untyped-call]

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._feature.set_value(False)  # type: ignore[no-untyped-call]

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_is_on = self._feature.value
