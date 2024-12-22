"""The Growatt server PV inverter sensor integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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


class GrowattSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Growatt Sensor."""

    _attr_has_entity_name = True
    coordinator: GrowattCoordinator
    entity_description: GrowattSensorEntityDescription

    def __init__(
        self,
        coordinator: GrowattCoordinator,
        device_name: str,
        serial_id: str,
        unique_id: str,
        description: GrowattSensorEntityDescription,
    ) -> None:
        """Initialize a Growatt sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:solar-power"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_id)}, manufacturer="Growatt", name=device_name
        )

    @property
    def native_value(self) -> int | float | None:
        """Return the value of the sensor."""
        result = self.coordinator.get_data(self.entity_description)
        if result is None:
            return None
        if self.entity_description.precision is not None:
            result = round(float(result), self.entity_description.precision)
        return result

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        if self.entity_description.currency:
            return self.coordinator.get_currency()
        return super().native_unit_of_measurement

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Growatt sensor."""
    config = {**config_entry.data}
    name = config[CONF_NAME]

    # Retrieve the coordinators from hass.data
    coordinators = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        GrowattSensor(
            coordinators["total"],
            device_name=f"{name} Total",
            serial_id=coordinators["total"].plant_id,
            unique_id=f"{coordinators['total'].plant_id}-{description.key}",
            description=description,
        )
        for description in TOTAL_SENSOR_TYPES
    ]

    # Add sensors for each device type
    for device_sn, device_coordinator in coordinators["devices"].items():
        sensor_descriptions: tuple[GrowattSensorEntityDescription, ...] = ()
        if device_coordinator.device_type == "inverter":
            sensor_descriptions = INVERTER_SENSOR_TYPES
        elif device_coordinator.device_type == "tlx":
            sensor_descriptions = TLX_SENSOR_TYPES
        elif device_coordinator.device_type == "storage":
            sensor_descriptions = STORAGE_SENSOR_TYPES
        elif device_coordinator.device_type == "mix":
            sensor_descriptions = MIX_SENSOR_TYPES
        else:
            _LOGGER.debug(
                "Device type %s was found but is not supported right now",
                device_coordinator.device_type,
            )
            continue

        entities.extend(
            [
                GrowattSensor(
                    device_coordinator,
                    device_name=device_sn,
                    serial_id=device_sn,
                    unique_id=f"{device_sn}-{description.key}",
                    description=description,
                )
                for description in sensor_descriptions
            ]
        )

    async_add_entities(entities, True)
