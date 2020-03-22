"""Support for Nexia / Trane XL Thermostats."""

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import ATTR_ATTRIBUTION

from .const import (
    ATTRIBUTION,
    DATA_NEXIA,
    DOMAIN,
    MANUFACTURER,
    NEXIA_DEVICE,
    UPDATE_COORDINATOR,
)
from .entity import NexiaEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors for a Nexia device."""

    nexia_data = hass.data[DOMAIN][config_entry.entry_id][DATA_NEXIA]
    nexia_home = nexia_data[NEXIA_DEVICE]
    coordinator = nexia_data[UPDATE_COORDINATOR]

    entities = []
    for thermostat_id in nexia_home.get_thermostat_ids():
        thermostat = nexia_home.get_thermostat_by_id(thermostat_id)
        entities.append(
            NexiaBinarySensor(
                coordinator, thermostat, "is_blower_active", "Blower Active"
            )
        )
        if thermostat.has_emergency_heat():
            entities.append(
                NexiaBinarySensor(
                    coordinator,
                    thermostat,
                    "is_emergency_heat_active",
                    "Emergency Heat Active",
                )
            )

    async_add_entities(entities, True)


class NexiaBinarySensor(NexiaEntity, BinarySensorDevice):
    """Provices Nexia BinarySensor support."""

    def __init__(self, coordinator, device, sensor_call, sensor_name):
        """Initialize the nexia sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._device = device
        self._name = f"{self._device.get_name()} {sensor_name}"
        self._call = sensor_call
        self._unique_id = f"{self._device.thermostat_id}_{sensor_call}"
        self._state = None

    @property
    def unique_id(self):
        """Return the unique id of the binary sensor."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._device.thermostat_id)},
            "name": self._device.get_name(),
            "model": self._device.get_model(),
            "sw_version": self._device.get_firmware(),
            "manufacturer": MANUFACTURER,
        }

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return getattr(self._device, self._call)()
