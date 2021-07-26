"""Platform for sensor integration."""

import re

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Config entry example."""
    # objects stored here by __init__.py
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    uuid = await api.async_get_uuid()

    #
    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    await coordinator.async_config_entry_first_refresh()

    sensors = []
    for twc in coordinator.data:
        for prop in coordinator.data[twc]:
            if prop in [
                "TWCID",
                "lastHeartbeat",
                # Skip properties retrieved from the car itself via Tesla's API
                "lastBatterySOC",
                "lastChargeLimit",
                "lastAtHome",
                "lastTimeToFullCharge",
            ]:
                continue
            sensors.append(TwcSensor(coordinator, uuid, twc, prop))
    async_add_entities(sensors)


class TwcSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, uuid, twc, prop):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._uuid = uuid
        self._twc = twc
        self._prop = prop
        self.entity_id = (
            "sensor." + DOMAIN + "_" + twc + "_" + self.__camel_to_snake(prop)
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return "TWC " + self._twc + " " + self._prop

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._uuid + "-" + self._twc + "-" + self._prop

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self._twc][self._prop]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if "amps" in self.entity_id:
            return ELECTRIC_CURRENT_AMPERE
        elif "volts" in self.entity_id:
            return (ELECTRIC_POTENTIAL_VOLT,)
        elif self.entity_id.endswith("_w"):
            return POWER_WATT
        elif "kwh" in self.entity_id:
            return ENERGY_KILO_WATT_HOUR
        else:
            return None

    @property
    def device_class(self):
        """Return the device class."""
        if "amps" in self.entity_id:
            return DEVICE_CLASS_CURRENT
        elif "volts" in self.entity_id:
            return DEVICE_CLASS_VOLTAGE
        elif self.entity_id.endswith("_w"):
            return DEVICE_CLASS_POWER
        elif "kwh" in self.entity_id:
            return DEVICE_CLASS_ENERGY
        else:
            return None

    @property
    def state_class(self):
        """Return the state class."""
        return "measurement"

    @staticmethod
    def __camel_to_snake(name: str):
        name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()
        return name.replace("k_wh", "_kwh")
