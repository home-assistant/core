"""Sensors on Zigbee Home Automation networks."""

from __future__ import annotations

from collections.abc import Mapping
import functools
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    EntityData,
    async_add_entities as zha_async_add_entities,
    exclude_none_values,
    get_zha_data,
)

_LOGGER = logging.getLogger(__name__)

# For backwards compatibility and transparency, all expected extra state attributes are
# explicitly listed below. These should have been sensors themselves but for whatever
# reason were not created as such. They will be migrated to independent sensor entities
# in a future release.
_EXTRA_STATE_ATTRIBUTES: set[str] = {
    # Battery
    "battery_size",
    "battery_quantity",
    "battery_voltage",
    # Power
    "measurement_type",
    "apparent_power_max",
    "rms_current_max",
    "rms_current_max_ph_b",
    "rms_current_max_ph_c",
    "rms_voltage_max",
    "rms_voltage_max_ph_b",
    "rms_voltage_max_ph_c",
    "ac_frequency_max",
    "power_factor_max",
    "power_factor_max_ph_b",
    "power_factor_max_ph_c",
    "active_power_max",
    "active_power_max_ph_b",
    "active_power_max_ph_c",
    # Smart Energy metering
    "device_type",
    "status",
    "zcl_unit_of_measurement",
    # Danfoss bitmaps
    "In_progress",
    "Valve_characteristic_found",
    "Valve_characteristic_lost",
    "Top_pcb_sensor_error",
    "Side_pcb_sensor_error",
    "Non_volatile_memory_error",
    "Unknown_hw_error",
    "Motor_error",
    "Invalid_internal_communication",
    "Invalid_clock_information",
    "Radio_communication_error",
    "Encoder_jammed",
    "Low_battery",
    "Critical_low_battery",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation sensor from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.SENSOR]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, Sensor, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Sensor(ZHAEntity, SensorEntity):
    """ZHA sensor."""

    def __init__(self, entity_data: EntityData, **kwargs: Any) -> None:
        """Initialize the ZHA select entity."""
        super().__init__(entity_data, **kwargs)
        entity = self.entity_data.entity

        if entity.device_class is not None:
            self._attr_device_class = SensorDeviceClass(entity.device_class)

        if entity.state_class is not None:
            self._attr_state_class = SensorStateClass(entity.state_class)

        if hasattr(entity.info_object, "unit") and entity.info_object.unit is not None:
            self._attr_native_unit_of_measurement = entity.info_object.unit

        if (
            hasattr(entity, "entity_description")
            and entity.entity_description is not None
        ):
            entity_description = entity.entity_description

            if entity_description.state_class is not None:
                self._attr_state_class = SensorStateClass(
                    entity_description.state_class.value
                )

            if entity_description.scale is not None:
                self._attr_scale = entity_description.scale

            if entity_description.native_unit_of_measurement is not None:
                self._attr_native_unit_of_measurement = (
                    entity_description.native_unit_of_measurement
                )

            if entity_description.device_class is not None:
                self._attr_device_class = SensorDeviceClass(
                    entity_description.device_class.value
                )

        if entity.info_object.suggested_display_precision is not None:
            self._attr_suggested_display_precision = (
                entity.info_object.suggested_display_precision
            )

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return self.entity_data.entity.native_value

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        entity = self.entity_data.entity
        if entity.extra_state_attribute_names is None:
            return None

        if not entity.extra_state_attribute_names <= _EXTRA_STATE_ATTRIBUTES:
            _LOGGER.warning(
                "Unexpected extra state attributes found for sensor %s: %s",
                entity,
                entity.extra_state_attribute_names - _EXTRA_STATE_ATTRIBUTES,
            )

        return exclude_none_values(
            {
                name: entity.state.get(name)
                for name in entity.extra_state_attribute_names
            }
        )
