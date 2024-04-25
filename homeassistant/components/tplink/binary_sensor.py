"""Support for TPLink binary sensors."""

from __future__ import annotations

from kasa import Feature, SmartDevice

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity, _entities_for_device_and_its_children
from .models import TPLinkData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    entities = _entities_for_device_and_its_children(
        device,
        feature_type=Feature.BinarySensor,
        entity_class=BinarySensor,
        coordinator=parent_coordinator,
    )

    async_add_entities(entities)


class BinarySensor(CoordinatedTPLinkEntity, BinarySensorEntity):
    """Representation of a TPLink binary sensor."""

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
        feature: Feature,
        parent: SmartDevice = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, coordinator, feature=feature, parent=parent)
        # TODO: generalize creation of entitydescription into CoordinatedTPLinkEntity?
        self.entity_description = BinarySensorEntityDescription(
            key=feature.id,
            translation_key=feature.id,
            name=feature.name,
            icon=feature.icon,
            entity_registry_enabled_default=feature.category
            is not Feature.Category.Debug,
        )

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_is_on = self._feature.value
