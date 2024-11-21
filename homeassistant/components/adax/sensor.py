"""Support for Adax energy sensors."""
import logging
import datetime
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Adax energy sensors from a config entry."""
    adax_data_handler = hass.data[entry.entry_id]
    sensors = []

    for room in adax_data_handler._rooms:
        sensors.append(AdaxEnergySensor(adax_data_handler, room))

    async_add_entities(sensors, True)

class AdaxEnergySensor(SensorEntity):
    """Representation of an Adax Energy Sensor."""

    def __init__(self, adax_data_handler, room):
        """Initialize the sensor."""
        self._adax_data_handler = adax_data_handler
        self._heater_data = room
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Adax Energy Sensor {self._heater_data['name']}"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"adax_energy_{self._heater_data['homeId']}_{self._heater_data['name']}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self):
        """Return the device class of the sensor."""
        return SensorStateClass.MEASUREMENT

    @property
    def last_reset(self):
        """Return the time when the sensor was last reset, if any."""
        return None

    async def async_update(self):
        """Get the latest data."""
        _LOGGER.debug("Updating AdaxEnergySensor for room ID %s", self._heater_data["id"])
        room = self._adax_data_handler.get_room(self._heater_data["id"])
        if room:
            self._heater_data = room
            self._state = room.get("energyWh", 0) / 1000
            _LOGGER.debug("Updated state: %s kWh", self._state)
        else:
            _LOGGER.warning("Room ID %s not found in data handler", self._heater_data["id"])
