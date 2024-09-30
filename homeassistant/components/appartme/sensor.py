"""Support for Appartme sensors."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Define the phases and their corresponding properties
PHASES = ["phase_1", "phase_2", "phase_3"]
MEASUREMENTS = {
    "current": {
        "unit": UnitOfElectricCurrent.AMPERE,
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "voltage": {
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "power": {
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Appartme sensor platform."""
    # Access the devices and API from hass.data
    data = hass.data[DOMAIN][config_entry.entry_id]
    devices_info = data["devices_info"]
    api = data["api"]
    coordinators = data["coordinators"]

    sensors = []
    for device_info in devices_info:
        device_id = device_info["deviceId"]
        coordinator = coordinators.get(device_id)
        if not coordinator:
            _LOGGER.warning("No coordinator found for device %s. Skipping", device_id)
            continue

        # First, add the individual phase sensors
        for phase in PHASES:
            for measurement, details in MEASUREMENTS.items():
                property_id = f"{phase}_{measurement}"
                # Check if the property exists and is readable
                sensors.extend(
                    [
                        AppartmeEnergySensor(
                            api,
                            device_info,
                            property_id,
                            coordinator,
                            unit=details["unit"],
                            device_class=details["device_class"],
                            state_class=details["state_class"],
                        )
                        for prop in device_info.get("properties", [])
                        if prop["propertyId"] == property_id and "read" in prop["mode"]
                    ]
                )
        # Now, add the total sensors
        for measurement, details in MEASUREMENTS.items():
            property_id = f"total_{measurement}"
            sensors.append(
                AppartmeEnergySensor(
                    api,
                    device_info,
                    property_id,
                    coordinator,
                    unit=details["unit"],
                    device_class=details["device_class"],
                    state_class=details["state_class"],
                )
            )

    if not sensors:
        _LOGGER.warning("No energy sensor entities to add")
        return

    # Add the sensor entities to Home Assistant
    async_add_entities(sensors)


class AppartmeEnergySensor(CoordinatorEntity, SensorEntity):
    """Representation of an Appartme energy sensor."""

    def __init__(
        self,
        api,
        device_info,
        property_id,
        coordinator,
        unit,
        device_class,
        state_class,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._api = api
        self._device_id = device_info["deviceId"]
        self._device_name = device_info["name"]
        self._property_id = property_id
        self._unit = unit
        self._device_class = device_class
        self._state_class = state_class
        self._attr_translation_key = property_id
        self._attr_has_entity_name = True

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link this entity to a device."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": "Appartme",
            "model": "Main Module",
            "sw_version": self._device_id,
        }

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{self._device_id}_{self._property_id}"

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        data = self.coordinator.data
        if data is None:
            return None

        if self._property_id.startswith("total_"):
            # This is a total sensor; compute the sum of the phase values
            measurement = self._property_id.split("_")[
                1
            ]  # 'current', 'voltage', 'power'
            total_value = 0
            for phase in PHASES:
                prop_id = f"{phase}_{measurement}"
                for prop in data.get("values", []):
                    if prop["propertyId"] == prop_id:
                        value = prop["value"]
                        if value is not None:
                            total_value += value
                        else:
                            # If any phase value is None, return None for total
                            return None
                        break  # Break inner loop once we've found the property
                else:
                    # If the property was not found in data, return None
                    return None
            return total_value
        # This is a regular phase sensor
        for prop in data.get("values", []):
            if prop["propertyId"] == self._property_id:
                return prop["value"]
        return None

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        return self._state_class

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
