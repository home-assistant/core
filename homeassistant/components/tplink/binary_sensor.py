"""Support for TPLink binary sensors."""
from __future__ import annotations

from kasa import Feature, FeatureCategory, FeatureType, SmartDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import legacy_device_id
from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity
from .models import TPLinkData


def _async_sensors_for_device(
    device: SmartDevice,
    coordinator: TPLinkDataUpdateCoordinator,
    has_parent: bool = False,
) -> list[BinarySensor]:
    """Generate the sensors for the device."""
    sensors = [
        BinarySensor(device, coordinator, id_, feat)
        for id_, feat in device.features.items()
        if feat.show_in_hass and feat.type == FeatureType.BinarySensor
    ]
    return sensors


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    children_coordinators = data.children_coordinators
    entities: list[BinarySensor] = []
    parent = parent_coordinator.device

    if parent.is_strip:
        # Historically we only add the children if the device is a strip
        for idx, child in enumerate(parent.children):
            entities.extend(
                _async_sensors_for_device(child, children_coordinators[idx], True)
            )
    else:
        entities.extend(_async_sensors_for_device(parent, parent_coordinator))

    async_add_entities(entities)


class BinarySensor(CoordinatedTPLinkEntity, BinarySensorEntity):
    """Representation of a TPLink binary sensor."""

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
        id_: str,
        feature: Feature,
    ) -> None:
        """Initialize the sensor."""
        # TODO: feature-based entities could be generalized
        super().__init__(device, coordinator)
        self._device = device
        self._feature = feature
        self._attr_unique_id = f"{legacy_device_id(device)}_new_{id_}"
        cat = (
            EntityCategory.DIAGNOSTIC
            if feature.category == FeatureCategory.Diagnostic
            else EntityCategory.CONFIG
        )
        _ = BinarySensorDeviceClass  # no-op to avoid pre-commit removing the import
        self.entity_description = BinarySensorEntityDescription(
            key=id_, name=feature.name, icon=feature.icon, entity_category=cat
        )
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_is_on = self._feature.value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()
