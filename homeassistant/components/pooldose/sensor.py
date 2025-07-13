"""Sensors for the Seko Pooldose integration.

Entities are enabled by default unless otherwise specified in the mapping.
"""

from __future__ import annotations

import logging
from typing import Any

from pooldose.request_handler import RequestStatus

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PooldoseConfigEntry
from .const import SENSOR_MAP, device_info
from .entity import PooldoseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PooldoseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PoolDose sensor entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    client = entry.runtime_data.client
    serialnumber = entry.data["serialnumber"]
    device_info_dict = entry.runtime_data.device_info

    entities: list[SensorEntity] = []

    for name, sensor in client.available_sensors().items():
        _LOGGER.debug("Sensor  %s: key=%s, type=%s", name, sensor.key, sensor.type)
        if sensor.conversion is not None:
            _LOGGER.debug("    conversion: %s", sensor.conversion)

        if name not in SENSOR_MAP:
            _LOGGER.debug("Sensor %s is not defined in SENSOR_MAP, skipping", name)
            continue

        device_class, entity_category, enabled = SENSOR_MAP[name]

        entities.append(
            PooldoseSensor(
                coordinator,
                client,
                name.lower(),
                name,
                None,
                device_class,
                serialnumber,
                entity_category,
                device_info_dict,
                enabled,
            )
        )

    async_add_entities(entities)


class PooldoseSensor(PooldoseEntity, SensorEntity):
    """Sensor entity for Seko PoolDose API."""

    def __init__(
        self,
        coordinator,
        client: Any,
        translation_key: str,
        key: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        serialnumber: str,
        entity_category: EntityCategory | None,
        device_info_dict: dict[str, Any],
        enabled_by_default: bool = True,
    ) -> None:
        """Initialize a PooldoseSensor entity."""
        super().__init__(
            coordinator,
            client,
            translation_key,
            key,
            serialnumber,
            device_info(device_info_dict),
            enabled_by_default,
        )
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_entity_category = entity_category
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def native_value(self) -> float | int | str | None:
        """Return the current value of the sensor."""
        if not self.coordinator.data:
            return None

        status, data = self.coordinator.data
        if status != RequestStatus.SUCCESS:
            _LOGGER.warning(
                "PoolDose API returned status %s, entities will be unavailable", status
            )
            return None

        if self._key not in data:
            _LOGGER.debug("Key %s not found in PoolDose API data", self._key)
            return None

        sensor_data = data[self._key]
        if not sensor_data:
            return None

        value = sensor_data[0]
        return value if value is not None else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement, dynamically determined from API data."""
        # Return static unit if set
        if self._attr_native_unit_of_measurement:
            return self._attr_native_unit_of_measurement

        # Try to get unit from coordinator data
        if not self.coordinator.data:
            return None

        status, data = self.coordinator.data
        sensor_data = data[self._key]
        if sensor_data and len(sensor_data) > 1:
            unit = sensor_data[1]
            if unit and unit != "UNDEFINED":
                return unit

        return None
