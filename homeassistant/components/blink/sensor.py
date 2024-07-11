"""Support for Blink system camera sensors."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_BRAND, DOMAIN, TYPE_TEMPERATURE, TYPE_WIFI_STRENGTH
from .coordinator import BlinkUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=TYPE_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TYPE_WIFI_STRENGTH,
        translation_key="wifi_strength",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize a Blink sensor."""

    coordinator: BlinkUpdateCoordinator = hass.data[DOMAIN][config.entry_id]
    entities = [
        BlinkSensor(coordinator, camera, description)
        for camera in coordinator.api.cameras
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class BlinkSensor(CoordinatorEntity[BlinkUpdateCoordinator], SensorEntity):
    """A Blink camera sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BlinkUpdateCoordinator,
        camera,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize sensors from Blink camera."""
        super().__init__(coordinator)
        self.entity_description = description

        self._camera = coordinator.api.cameras[camera]
        serial = self._camera.serial
        self._attr_unique_id = f"{serial}-{description.key}"
        self._sensor_key = (
            "temperature_calibrated"
            if description.key == "temperature"
            else description.key
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            serial_number=serial,
            name=f"{DOMAIN} {camera}",
            manufacturer=DEFAULT_BRAND,
            model=self._camera.camera_type,
        )
        self._update_attr()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self._update_attr()
        super()._handle_coordinator_update()

    @callback
    def _update_attr(self) -> None:
        """Update attributes for sensor."""
        try:
            self._attr_native_value = self._camera.attributes[self._sensor_key]
            _LOGGER.debug(
                "'%s' %s = %s",
                self._camera.attributes["name"],
                self._sensor_key,
                self._attr_native_value,
            )
        except KeyError:
            self._attr_native_value = None
            _LOGGER.error(
                "%s not a valid camera attribute. Did the API change?", self._sensor_key
            )
