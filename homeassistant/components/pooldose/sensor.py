"""Sensors for the Seko Pooldose integration.

Entities are enabled by default unless otherwise specified in the mapping.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import SENSOR_MAP, STATIC_SENSOR_KEYS, VALUE_CONVERSION_TABLE, device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pooldose sensor entities from a config entry."""
    data = hass.data["pooldose"][entry.entry_id]
    coordinator: DataUpdateCoordinator[dict[str, Any]] = data["coordinator"]
    api = data["api"]
    serialnumber = entry.data["serialnumber"]
    device_info_dict = data.get("device_info", {})

    entities: list[SensorEntity] = []
    for uid, (
        translation_key,
        unit,
        device_class,
        key,
        entity_category,
        enabled_by_default,
    ) in SENSOR_MAP.items():
        if key in STATIC_SENSOR_KEYS:
            entities.append(
                PooldoseStaticSensor(
                    coordinator,
                    api,
                    translation_key,
                    uid,
                    key,
                    serialnumber,
                    entity_category,
                    device_info_dict,
                    enabled_by_default,
                )
            )
        else:
            entities.append(
                PooldoseSensor(
                    coordinator,
                    api,
                    translation_key,
                    uid,
                    key,
                    unit,
                    SensorDeviceClass(device_class) if device_class else None,
                    serialnumber,
                    entity_category,
                    device_info_dict,
                    enabled_by_default,
                )
            )
    async_add_entities(entities)


class PooldoseSensor(CoordinatorEntity, SensorEntity):
    """Sensor entity for Seko Pooldose API."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        api: Any,
        translation_key: str,
        uid: str,
        key: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        serialnumber: str,
        entity_category: EntityCategory | None,
        device_info_dict: dict[str, Any],
        enabled_by_default: bool = True,
    ) -> None:
        """Initialize a PooldoseSensor entity."""
        super().__init__(coordinator)
        self._api = api
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{serialnumber}_{key}"
        self._key = key
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_entity_category = entity_category
        self._attr_device_info = device_info(device_info_dict)
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def native_value(self) -> float | int | str | None:
        """Return the current value of the sensor, optionally converted."""
        try:
            value = self.coordinator.data["devicedata"][self._api.serial_key][
                self._key
            ]["current"]
        except (KeyError, TypeError):
            return None
        # Value conversion if mapping exists
        if self._key in VALUE_CONVERSION_TABLE:
            return VALUE_CONVERSION_TABLE[self._key].get(str(value), value)
        return value


class PooldoseStaticSensor(CoordinatorEntity, SensorEntity):
    """Static sensor entity for Pooldose device info."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        api: Any,
        translation_key: str,
        uid: str,
        key: str,
        serialnumber: str,
        entity_category: EntityCategory | None,
        device_info_dict: dict[str, Any],
        enabled_by_default: bool = True,
    ) -> None:
        """Initialize a static Pooldose sensor entity."""
        super().__init__(coordinator)
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{serialnumber}_{key}"
        self._key = key
        self._attr_entity_category = entity_category
        self._device_info_dict = device_info_dict
        self._attr_device_info = device_info(device_info_dict)
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def native_value(self) -> str | None:
        """Return the static value from device info."""
        return self._device_info_dict.get(self._key)
