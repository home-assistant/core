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
from .entity import CoordinatedTPLinkEntity
from .models import TPLinkData


def _async_sensors_for_device(
    device: SmartDevice,
    coordinator: TPLinkDataUpdateCoordinator,
    parent: SmartDevice = None,
) -> list[BinarySensor]:
    """Generate the sensors for the device."""
    return [
        BinarySensor(device, coordinator, feat, parent=parent)
        for id_, feat in device.features.items()
        if feat.type == Feature.BinarySensor
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    entities: list[BinarySensor] = []
    device = parent_coordinator.device

    entities.extend(_async_sensors_for_device(device, parent_coordinator))

    for child in device.children:
        entities.extend(
            _async_sensors_for_device(child, parent_coordinator, parent=device)
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
