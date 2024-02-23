"""Support for TPLink binary sensors."""
from __future__ import annotations

from kasa import Feature, FeatureType, SmartDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
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
    parent: SmartDevice = None,
) -> list[BinarySensor]:
    """Generate the sensors for the device."""
    sensors = [
        BinarySensor(device, coordinator, id_, feat, parent=parent)
        for id_, feat in device.features.items()
        if feat.type == FeatureType.BinarySensor
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
        id_: str,
        feature: Feature,
        parent: SmartDevice = None,
    ) -> None:
        """Initialize the sensor."""
        # TODO: feature-based entities could be generalized
        super().__init__(device, coordinator, parent=parent)
        self._device = device
        self._feature = feature
        self._attr_unique_id = f"{legacy_device_id(device)}_new_{id_}"
        _ = BinarySensorDeviceClass  # TODO: no-op to avoid pre-commit removing the import
        self.entity_description = BinarySensorEntityDescription(
            key=id_, name=feature.name, icon=feature.icon
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
