"""Support for TPLink switch entities."""

from __future__ import annotations

import logging
from typing import Any

from kasa import Device, Feature

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TPLinkConfigEntry
from .coordinator import TPLinkDataUpdateCoordinator
from .descriptions import TPLinkSwitchEntityDescription
from .entity import (
    CoordinatedTPLinkEntity,
    _entities_for_device_and_its_children,
    async_refresh_after,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    entities = _entities_for_device_and_its_children(
        device,
        coordinator=parent_coordinator,
        feature_type=Feature.Switch,
        entity_class=TPLinkSwitch,
    )

    async_add_entities(entities)


class TPLinkSwitch(CoordinatedTPLinkEntity, SwitchEntity):
    """Representation of a feature-based TPLink switch."""

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        *,
        description: TPLinkSwitchEntityDescription,
        feature: Feature,
        parent: Device | None = None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            device,
            coordinator,
            description=description,
            feature=feature,
            parent=parent,
        )
        self._feature: Feature

        # Use the device name for the primary switch control
        if feature.category is Feature.Category.Primary and not parent:
            self._attr_name = None

        self._async_call_update_attrs()

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._feature.set_value(True)

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._feature.set_value(False)

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_is_on = self._feature.value
