"""Support for TPLink switch entities."""

from __future__ import annotations

import logging
from typing import Any, cast

from kasa import Feature, SmartDevice, SmartPlug

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity, async_refresh_after
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
    device = cast(SmartPlug, parent_coordinator.device)
    entities: list = []

    def _switches_for_device(dev, parent: SmartDevice = None) -> list[Switch]:
        return [
            Switch(dev, data.parent_coordinator, feat, parent=parent)
            for feat in dev.features.values()
            if feat.type == Feature.Switch
        ]
        # TODO: a way to filter state switch for platforms with their own main controls:
        #  lights and fans?

    if device.children:
        _LOGGER.debug("Initializing device with %s children", len(device.children))
        for child in device.children:
            entities.extend(_switches_for_device(child, parent=device))

    entities.extend(_switches_for_device(device))

    async_add_entities(entities)


class Switch(CoordinatedTPLinkEntity, SwitchEntity):
    """Representation of a feature-based TPLink sensor."""

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
        feature: Feature,
        parent: SmartDevice = None,
    ):
        """Initialize the switch."""
        super().__init__(device, coordinator, feature=feature, parent=parent)
        # TODO: generalize creation of entitydescription into CoordinatedTPLinkEntity?
        self.entity_description = SwitchEntityDescription(
            key=feature.id,
            translation_key=feature.id,
            name=feature.name,
            icon=feature.icon,
            entity_registry_enabled_default=feature.category
            is not Feature.Category.Debug,
        )

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the LED switch on."""
        await self._feature.set_value(True)

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the LED switch off."""
        await self._feature.set_value(False)

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_is_on = self._feature.value
