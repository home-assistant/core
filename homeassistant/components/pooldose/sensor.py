"""Sensors for the Seko Pooldose integration.

Entities are enabled by default unless otherwise specified in the mapping.
"""

from __future__ import annotations

import logging
from typing import Any

from pooldose.request_handler import RequestStatus

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DYNAMIC_SENSOR_MAP, STATIC_SENSOR_MAP, device_info
from .entity import PooldoseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PoolDose sensor entities from a config entry."""
    data = hass.data["pooldose"][entry.entry_id]
    coordinator: DataUpdateCoordinator[dict[str, Any]] = data["coordinator"]
    client = data["client"]
    serialnumber = entry.data["serialnumber"]
    device_info_dict = data.get("device_info", {})

    entities: list[SensorEntity] = []

    # static sensors for device info entries
    # These sensors are not dynamic and do not require updates from the API.
    for name in client.device_info:
        _LOGGER.debug("Static sensor %s: key=%s", name, client.device_info[name])
        if name not in STATIC_SENSOR_MAP:
            _LOGGER.debug(
                "Static sensor %s is not defined in SENSOR_MAP, skipping", name
            )
            continue

        device_class, entity_category, enabled = STATIC_SENSOR_MAP[name]
        entities.append(
            PooldoseStaticSensor(
                coordinator,
                client,
                name.lower(),  # translation_key
                name,  # key
                device_class,
                serialnumber,
                entity_category,
                device_info_dict,
                enabled,
            )
        )

    # dynamic sensors
    for name, sensor in client.available_sensors().items():
        _LOGGER.debug("Sensor  %s: key=%s, type=%s", name, sensor.key, sensor.type)
        if sensor.conversion is not None:
            _LOGGER.debug("    conversion: %s", sensor.conversion)

        if name not in DYNAMIC_SENSOR_MAP:
            _LOGGER.debug(
                "Dynamic sensor %s is not defined in SENSOR_MAP, skipping", name
            )
            continue

        device_class, entity_category, enabled = DYNAMIC_SENSOR_MAP[name]

        entities.append(
            PooldoseSensor(
                coordinator,
                client,
                name.lower(),  # translation_key is the same as key for dynamic sensors
                name,  # key
                None,  # sensor.unit,
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
        coordinator: DataUpdateCoordinator[dict[str, Any]],
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
            _LOGGER.warning(
                "Key %s not found in PoolDose API data, entities will be unavailable",
                self._key,
            )
            return None
        sensor_data = data[self._key]
        if not sensor_data:
            return None

        value = sensor_data[0]
        return value if value is not None else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement, dynamically determined from API data."""
        # Falls bereits statisch gesetzt (z.B. °C), verwende das
        if self._attr_native_unit_of_measurement:
            return self._attr_native_unit_of_measurement

        # Ansonsten versuche es aus den API-Daten zu lesen
        if not self.coordinator.data:
            return None

        status, data = self.coordinator.data
        sensor_data = data[self._key]
        if sensor_data and len(sensor_data) > 1:
            unit = sensor_data[1]
            if unit and unit != "UNDEFINED":
                return unit

        return None


class PooldoseStaticSensor(PooldoseEntity, SensorEntity):
    """Static sensor entity for PoolDose device info."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        client: Any,
        translation_key: str,
        key: str,
        device_class: SensorDeviceClass | None,
        serialnumber: str,
        entity_category: EntityCategory | None,
        device_info_dict: dict[str, Any],
        enabled_by_default: bool = True,
    ) -> None:
        """Initialize a static Pooldose sensor entity."""
        super().__init__(
            coordinator,
            client,
            translation_key,
            key,
            serialnumber,
            device_info(device_info_dict),
            enabled_by_default,
        )
        self._attr_device_class = device_class
        self._attr_entity_category = entity_category
        self._attr_entity_registry_enabled_default = enabled_by_default
        self._device_info_dict = device_info_dict

    @property
    def native_value(self) -> str | None:
        """Return the static value from device info."""
        return self._device_info_dict.get(self._key)
