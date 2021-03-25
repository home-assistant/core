"""Support for KEBA charging station sensors."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_POWER,
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
)

from . import DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the KEBA charging station platform."""
    if discovery_info is None:
        return

    keba = hass.data[DOMAIN]

    sensors = [
        KebaSensor(
            keba,
            "Curr user",
            "Max Current",
            "max_current",
            "mdi:flash",
            ELECTRICAL_CURRENT_AMPERE,
        ),
        KebaSensor(
            keba,
            "Setenergy",
            "Energy Target",
            "energy_target",
            "mdi:gauge",
            ENERGY_KILO_WATT_HOUR,
        ),
        KebaSensor(
            keba,
            "P",
            "Charging Power",
            "charging_power",
            "mdi:flash",
            "kW",
            DEVICE_CLASS_POWER,
        ),
        KebaSensor(
            keba,
            "E pres",
            "Session Energy",
            "session_energy",
            "mdi:gauge",
            ENERGY_KILO_WATT_HOUR,
        ),
        KebaSensor(
            keba,
            "E total",
            "Total Energy",
            "total_energy",
            "mdi:gauge",
            ENERGY_KILO_WATT_HOUR,
        ),
    ]
    async_add_entities(sensors)


class KebaSensor(SensorEntity):
    """The entity class for KEBA charging stations sensors."""

    def __init__(self, keba, key, name, entity_type, icon, unit, device_class=None):
        """Initialize the KEBA Sensor."""
        self._keba = keba
        self._key = key
        self._name = name
        self._entity_type = entity_type
        self._icon = icon
        self._unit = unit
        self._device_class = device_class

        self._state = None
        self._attributes = {}

    @property
    def should_poll(self):
        """Deactivate polling. Data updated by KebaHandler."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the binary sensor."""
        return f"{self._keba.device_id}_{self._entity_type}"

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self._keba.device_name} {self._name}"

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Get the unit of measurement."""
        return self._unit

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the binary sensor."""
        return self._attributes

    async def async_update(self):
        """Get latest cached states from the device."""
        self._state = self._keba.get_value(self._key)

        if self._key == "P":
            self._attributes["power_factor"] = self._keba.get_value("PF")
            self._attributes["voltage_u1"] = str(self._keba.get_value("U1"))
            self._attributes["voltage_u2"] = str(self._keba.get_value("U2"))
            self._attributes["voltage_u3"] = str(self._keba.get_value("U3"))
            self._attributes["current_i1"] = str(self._keba.get_value("I1"))
            self._attributes["current_i2"] = str(self._keba.get_value("I2"))
            self._attributes["current_i3"] = str(self._keba.get_value("I3"))
        elif self._key == "Curr user":
            self._attributes["max_current_hardware"] = self._keba.get_value("Curr HW")

    def update_callback(self):
        """Schedule a state update."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Add update callback after being added to hass."""
        self._keba.add_update_listener(self.update_callback)
