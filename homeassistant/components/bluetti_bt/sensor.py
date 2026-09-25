"""Sensor for Bluetti BT integration."""

from decimal import Decimal
from enum import Enum
import logging
from typing import override

from bluetti_bt_lib import FieldName

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL, DOMAIN, ENTITY_DETAILS_MAPPING, DetailsMapping
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
            field_name=field.name,
            details=ENTITY_DETAILS_MAPPING[FieldName(field.name)],
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
        field_name: str,
        details: DetailsMapping,
    ) -> None:
        """Init sensor entity."""

        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_unique_id = f"{device_info.get('serial_number')}_{field_name}"
        self._attr_device_info = device_info
        self._attr_has_entity_name = True
        self._attr_translation_key = field_name

        self._attr_native_unit_of_measurement = details.unit
        self._attr_entity_category = details.category
        self._attr_device_class = details.device_class
        self._attr_state_class = details.state_class

        self._logger = logging.getLogger(f"{DOMAIN}")

    @override
    async def async_added_to_hass(self) -> None:
        """Update the entity from the coordinator's initial refresh."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        if not self.coordinator.data:
            self._logger.warning(
                "Data from coordinator is Empty",
            )
            return

        if not isinstance(self.coordinator.data, dict):
            self._logger.warning(
                "Invalid data from coordinator (sensor.%s)",
                self._attr_unique_id,
            )
            return

        self._logger.debug(
            "Coordinator data: %s",
            self.coordinator.data,
        )

        response_data = self.coordinator.data.get(str(self._attr_translation_key))

        if response_data is None:
            self._logger.debug(
                "No data available for (%s)", str(self._attr_translation_key)
            )
            self._attr_native_value = None
            self.async_write_ha_state()
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
            return

        if isinstance(response_data, Enum):
            self._attr_native_value = response_data.name
        else:
            self._attr_native_value = response_data
        self.async_write_ha_state()
