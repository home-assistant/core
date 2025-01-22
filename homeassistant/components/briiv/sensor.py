"""Support for Briiv sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import _LOGGER, HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BriivAPI
from .const import DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temp",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humid",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm1",
        translation_key="pm1",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm2_5",
        translation_key="pm2_5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm10",
        translation_key="pm10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voc",
        translation_key="voc",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co",
        translation_key="carbon_monoxide",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.CO,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="nox",
        translation_key="nitrogen_oxides",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.NITROUS_OXIDE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Briiv sensors."""
    api: BriivAPI = hass.data[DOMAIN][entry.entry_id]

    # Start listening for updates
    await api.start_listening(hass.loop)

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
            _LOGGER.debug(
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
