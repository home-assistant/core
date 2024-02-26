"""Support for TPLink number entities."""
from __future__ import annotations

import logging
from typing import cast

from kasa import Feature, FeatureType, SmartDevice, SmartPlug

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import legacy_device_id
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
    """Set up number entities."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    device = cast(SmartPlug, parent_coordinator.device)
    entities: list = []

    def _numbers_for_device(dev, parent: SmartDevice = None) -> list[Number]:
        switches = [
            Number(dev, data.parent_coordinator, id_, feat, parent=parent)
            for id_, feat in dev.features.items()
            if feat.type == FeatureType.Number
        ]
        return switches

    if device.children:
        _LOGGER.debug("Initializing device with %s children", len(device.children))
        for child in device.children:
            entities.extend(_numbers_for_device(child, parent=device))

    entities.extend(_numbers_for_device(device))

    async_add_entities(entities)


class Number(CoordinatedTPLinkEntity, NumberEntity):
    """Representation of a feature-based TPLink sensor."""

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
        id_: str,
        feature: Feature,
        parent: SmartDevice = None,
    ):
        """Initialize the number entity."""
        super().__init__(device, coordinator, parent=parent)
        self._device = device
        self._feature = feature
        self._attr_unique_id = f"{legacy_device_id(device)}_new_{id_}"
        self._attr_entity_category = (
            EntityCategory.CONFIG
        )  # TODO: read from the feature

        self.entity_description = NumberEntityDescription(
            key=id_,
            translation_key=id_,
            name=feature.name,
            icon=feature.icon,
            native_min_value=feature.minimum_value,
            native_max_value=feature.maximum_value,
        )
        self._async_update_attrs()

    @async_refresh_after
    async def async_set_native_value(self, value: float) -> None:
        """Set feature value."""
        await self._feature.set_value(int(value))

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_native_value = self._feature.value
