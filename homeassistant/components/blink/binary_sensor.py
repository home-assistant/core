"""Support for Blink system camera control."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEFAULT_BRAND,
    DOMAIN,
    TYPE_BATTERY,
    TYPE_CAMERA_ARMED,
    TYPE_MOTION_DETECTED,
)
from .coordinator import BlinkConfigEntry, BlinkUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

BINARY_SENSORS_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=TYPE_BATTERY,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Camera Armed sensor is deprecated covered by switch and will be removed in 2023.6.
    BinarySensorEntityDescription(
        key=TYPE_CAMERA_ARMED,
        translation_key="camera_armed",
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key=TYPE_MOTION_DETECTED,
        device_class=BinarySensorDeviceClass.MOTION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BlinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the blink binary sensors."""

    coordinator = config_entry.runtime_data

    entities = [
        BlinkBinarySensor(coordinator, camera, description)
        for camera in coordinator.api.cameras
        for description in BINARY_SENSORS_TYPES
    ]
    async_add_entities(entities)


class BlinkBinarySensor(CoordinatorEntity[BlinkUpdateCoordinator], BinarySensorEntity):
    """Representation of a Blink binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BlinkUpdateCoordinator,
        camera,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._camera = coordinator.api.cameras[camera]
        serial = self._camera.serial
        self._attr_unique_id = f"{serial}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            serial_number=serial,
            name=camera,
            manufacturer=DEFAULT_BRAND,
            model=self._camera.camera_type,
        )
        self._update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update from data coordinator."""
        self._update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _update_attrs(self) -> None:
        """Update attributes for binary sensor."""
        is_on = self._camera.attributes[self.entity_description.key]
        _LOGGER.debug(
            "'%s' %s = %s",
            self._camera.attributes["name"],
            self.entity_description.key,
            is_on,
        )
        if self.entity_description.key == TYPE_BATTERY:
            is_on = is_on != "ok"
        self._attr_is_on = is_on
