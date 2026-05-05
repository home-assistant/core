# pylint: disable=duplicate-code
"""Creates Sensor entities for the my-PV Home Assistant integration."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MyPVCoordinator
from .const import (
    ENTITY_CATEGORIES,
    RESERVED_KEYS,
    SENSOR_DEVICE_CLASSES,
    SENSOR_STATE_CLASSES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV sensor."""
    coordinator: MyPVCoordinator = config_entry.runtime_data
    entities = []

    for key, config in coordinator.data_configurations:
        if config.get("type") != "boolean" and key not in RESERVED_KEYS:
            device_class = None
            options = None
            state_class = None
            if config.get("type") == "enumeration":
                device_class = SensorDeviceClass.ENUM
                options = list(config.get("options").keys())
            elif config.get("type") == "string":
                device_class = SENSOR_DEVICE_CLASSES.get(key)
            else:
                device_class = SENSOR_DEVICE_CLASSES.get(key)
                state_class = SENSOR_STATE_CLASSES.get(
                    key, SensorStateClass.MEASUREMENT
                )

            entity_category = ENTITY_CATEGORIES.get(key)

            translation_key = key
            if key == "curr_mains" and coordinator.supports_data("curr_l2"):
                translation_key = "curr_l1"
            elif key == "volt_mains" and coordinator.supports_data("volt_l2"):
                translation_key = "volt_l1"
            elif key == "temp1" and not coordinator.supports_data("temp2"):
                translation_key = "temp"

            entity_description = SensorEntityDescription(
                key=key,
                device_class=device_class,
                entity_category=entity_category,
                translation_key=translation_key,
                native_unit_of_measurement=config.get("unit"),
                options=options,
                state_class=state_class,
            )
            entities.append(
                MyPVSensor(
                    coordinator,
                    entity_description,
                    config_entry.entry_id,
                )
            )

    async_add_entities(entities)


class MyPVSensor(CoordinatorEntity, SensorEntity):
    """Base my-PV Sensor."""

    _attr_has_entity_name = True
    _attr_available = False

    coordinator: MyPVCoordinator

    def __init__(
        self,
        coordinator: MyPVCoordinator,
        entity_description: SensorEntityDescription,
        config_entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description.key)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{config_entry_id}-{entity_description.key}"

        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        """Called when sensor is added to Home Assistant."""
        await super().async_added_to_hass()

        self._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self._attr_available:
            return self._attr_available

        return self.coordinator.last_update_success

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.connected:
            self._attr_available = False
        else:
            value = self.coordinator.get_data_value(self.entity_description.key)
            if value is None:
                self._attr_available = False
            else:
                self._attr_native_value = value
                self._attr_available = True

        self.async_write_ha_state()
