"""Read status of growatt inverters."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN
from ..coordinator import GrowattCoordinator
from .inverter import INVERTER_SENSOR_TYPES
from .mix import MIX_SENSOR_TYPES
from .sensor_entity_description import GrowattSensorEntityDescription
from .storage import STORAGE_SENSOR_TYPES
from .tlx import TLX_SENSOR_TYPES
from .total import TOTAL_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Growatt sensor."""
    # Use runtime_data instead of hass.data
    data = config_entry.runtime_data

    entities: list[GrowattSensor] = []

    # Add total sensors
    total_coordinator = data.total_coordinator
    entities.extend(
        GrowattSensor(
            total_coordinator,
            name=f"{config_entry.data['name']} Total",
            serial_id=config_entry.data["plant_id"],
            unique_id=f"{config_entry.data['plant_id']}-{description.key}",
            description=description,
        )
        for description in TOTAL_SENSOR_TYPES
    )

    # Add sensors for each device
    for device_sn, device_coordinator in data.devices.items():
        sensor_descriptions: list = []
        if device_coordinator.device_type == "inverter":
            sensor_descriptions = list(INVERTER_SENSOR_TYPES)
        elif device_coordinator.device_type == "tlx":
            sensor_descriptions = list(TLX_SENSOR_TYPES)
        elif device_coordinator.device_type == "storage":
            sensor_descriptions = list(STORAGE_SENSOR_TYPES)
        elif device_coordinator.device_type == "mix":
            sensor_descriptions = list(MIX_SENSOR_TYPES)
        else:
            _LOGGER.debug(
                "Device type %s was found but is not supported right now",
                device_coordinator.device_type,
            )

        entities.extend(
            [
                GrowattSensor(
                    device_coordinator,
                    name=device_sn,
                    serial_id=device_sn,
                    unique_id=f"{device_sn}-{description.key}",
                    description=description,
                )
                for description in sensor_descriptions
            ]
        )

    async_add_entities(entities)


class GrowattSensor(CoordinatorEntity[GrowattCoordinator], SensorEntity):
    """Representation of a Growatt Sensor."""

    _attr_has_entity_name = True
    coordinator: GrowattCoordinator
    entity_description: GrowattSensorEntityDescription

    def __init__(
        self,
        coordinator: GrowattCoordinator,
        name: str,
        serial_id: str,
        unique_id: str,
        description: GrowattSensorEntityDescription,
    ) -> None:
        """Initialize a PVOutput sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:solar-power"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_id)},
            manufacturer="Growatt",
            name=name,
        )

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        result = self.coordinator.get_data(self.entity_description)
        if self.entity_description.precision is not None:
            result = round(result, self.entity_description.precision)
        return result

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if self.entity_description.currency:
            return self.coordinator.get_currency()
        return super().native_unit_of_measurement
