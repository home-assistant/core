"""Sensor for Bluetti BT integration."""

from decimal import Decimal
from enum import Enum
import logging
from typing import override

from bluetti_bt_lib import DeviceField

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import CONF_ADDRESS, CONF_MODEL, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL, DOMAIN
from .coordinator import BluettiBtConfigEntry, PollingCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BluettiBtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup sensor entities."""

    device = entry.runtime_data.device
    sensor_fields = device.get_sensor_fields()

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.data.get(CONF_ADDRESS, ""))},
        manufacturer="Bluetti",
        model=entry.data.get(CONF_MODEL),
        serial_number=str(entry.data.get(CONF_SERIAL)),
    )

    sensors_to_add: list[BluettiSensor] = [
        BluettiSensor(
            entry.runtime_data,
            device_info,
            field,
        )
        for field in sensor_fields
    ]

    async_add_entities(sensors_to_add)


class BluettiSensor(CoordinatorEntity, SensorEntity):
    """Bluetti universal sensor."""

    def __init__(
        self,
        coordinator: PollingCoordinator,
        device_info: DeviceInfo,
        field: DeviceField,
    ) -> None:
        """Init sensor entity."""

        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_unique_id = f"{device_info.get('serial_number')}_{field.name}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True
        self._attr_translation_key = field.name

        self._attr_native_unit_of_measurement = field.unit
        self._attr_entity_category = (
            EntityCategory(field.category) if field.category is not None else None
        )
        self._attr_device_class = (
            SensorDeviceClass(field.sensor) if field.sensor is not None else None
        )
        self._attr_state_class = field.state_type

        self._logger = logging.getLogger(f"{DOMAIN}")
        self._unavailable_counter = 0
        self._attr_available = False

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return self._attr_available

    def _set_available(self):
        """Set sensor as available."""
        self._attr_available = True
        self._unavailable_counter = 0
        self.async_write_ha_state()

    def _set_unavailable(self):
        """Set sensor as unavailable."""
        self._unavailable_counter += 1

        if self._unavailable_counter >= 5:
            self._attr_available = False

        self.async_write_ha_state()

    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        if not self.coordinator.data:
            self._logger.warning(
                "Data from coordinator is Empty",
            )
            self._set_unavailable()
            return

        if not isinstance(self.coordinator.data, dict):
            self._logger.warning(
                "Invalid data from coordinator (sensor.%s)",
                self._attr_unique_id,
            )
            self._set_unavailable("Invalid data")
            return

        self._logger.debug(
            "Coordinator data: %s",
            self.coordinator.data,
        )

        response_data = self.coordinator.data.get(str(self._attr_translation_key))

        if response_data is None:
            self._logger.debug(
                "No data for available for (%s)", str(self._attr_translation_key)
            )
            self._set_unavailable()
            return

        if (
            not isinstance(response_data, int)
            and not isinstance(response_data, float)
            and not isinstance(response_data, Decimal)
            and not isinstance(response_data, Enum)
            and not isinstance(response_data, str)
        ):
            self._logger.warning(
                "Invalid response data type from coordinator (sensor.%s): %s has type %s",
                self._attr_unique_id,
                response_data,
                type(response_data),
            )
            self._set_unavailable()
            return

        self._set_available()

        # Different for enum and numeric
        if isinstance(response_data, Enum):
            # Enum
            self._attr_native_value = response_data.name
        else:
            # Numeric
            self._attr_native_value = response_data
        self.async_write_ha_state()
