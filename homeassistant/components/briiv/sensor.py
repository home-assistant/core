"""Support for Briiv sensors."""

from __future__ import annotations

from typing import Any

from pybriiv import BriivAPI

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BriivConfigEntry  # Add this import
from .const import DOMAIN, LOGGER, SENSOR_TYPES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BriivConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Briiv sensors."""
    api: BriivAPI = entry.runtime_data.api

    # Get serial number from entry data
    serial_number = entry.data["serial_number"]

    async_add_entities(
        [
            BriivSensor(api, description, entry, serial_number)
            for description in SENSOR_TYPES
        ]
    )


class BriivSensor(SensorEntity):
    """Representation of a Briiv sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api: BriivAPI,
        description: SensorEntityDescription,
        entry: ConfigEntry,
        serial_number: str,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._api = api
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=f"Briiv {serial_number}",
            manufacturer="Briiv",
            model="Air Filter",
        )
        self._attr_native_value = None
        api.register_callback(self._handle_update)

    async def _handle_update(self, data: dict[str, Any]) -> None:
        """Handle updated data from device."""
        if "serial_number" in data:
            LOGGER.debug(
                "Sensor %s_%s received update - Device SN: %s, Has key: %s, Value: %s",
                self._serial_number,
                self.entity_description.key,
                data.get("serial_number"),
                self.entity_description.key in data,
                data.get(self.entity_description.key),
            )

        # Check if this update is for our device
        if (
            "serial_number" in data
            and data["serial_number"] == self._serial_number
            and self.entity_description.key in data
        ):
            self._attr_native_value = data[self.entity_description.key]
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Remove callback when entity is being removed."""
        self._api.remove_callback(self._handle_update)
