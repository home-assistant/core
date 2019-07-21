"""Support for KEBA charging station sensors."""
import logging

from homeassistant.const import ENERGY_KILO_WATT_HOUR
from homeassistant.helpers.entity import Entity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config,
                               async_add_entities, discovery_info=None):
    """Set up the KEBA charging station platform."""
    _LOGGER.debug("Initializing KEBA charging station sensors")
    keba = hass.data[DOMAIN]

    sensors = [
        KebaSensor(keba, 'Curr user', 'Max current', 'mdi:flash',
                   'A'),
        KebaSensor(keba, 'Setenergy', 'Energy target', 'mdi:gauge',
                   ENERGY_KILO_WATT_HOUR),
        KebaSensor(keba, 'P', 'Charging power', 'mdi:flash',
                   'kW'),
        KebaSensor(keba, 'E pres', 'Session energy', 'mdi:gauge',
                   ENERGY_KILO_WATT_HOUR),
        KebaSensor(keba, 'E total', 'Total Energy', 'mdi:gauge',
                   ENERGY_KILO_WATT_HOUR)
    ]
    async_add_entities(sensors)


class KebaSensor(Entity):
    """The entity class for KEBA charging stations sensors."""

    def __init__(self, keba, key, name, icon, unit):
        """Initialize the KEBA Sensor."""
        self._key = key
        self._keba = keba
        self._name = name
        self._icon = icon
        self._unit = unit
        self._state = None
        self._attributes = {}

    @property
    def should_poll(self):
        """Deactivate polling. Data updated by KebaHandler."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the binary sensor."""
        return self._keba.device_name + '_' + self._name

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

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
    def device_state_attributes(self):
        """Return the state attributes of the binary sensor."""
        return self._attributes.items()

    async def async_update(self):
        """Get latest cached states from the device."""
        self._state = self._keba.get_value(self._key)

        if self._key == 'P':
            self._attributes['Power Factor cos(phi)'] = \
                self._keba.get_value('PF')
            self._attributes['Voltage U1 (V)'] = \
                str(self._keba.get_value('U1'))
            self._attributes['Voltage U2 (V)'] = \
                str(self._keba.get_value('U2'))
            self._attributes['Voltage U3 (V)'] = \
                str(self._keba.get_value('U3'))
            self._attributes['Current I1 (A)'] = \
                str(self._keba.get_value('I1'))
            self._attributes['Current I2 (A)'] = \
                str(self._keba.get_value('I2'))
            self._attributes['Current I3 (A)'] = \
                str(self._keba.get_value('I3'))
        elif self._key == 'Curr user':
            self._attributes['Maximum current allowed (A)'] = \
                self._keba.get_value('Curr HW')

    def update_callback(self):
        """Schedule a state update."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Add callback after being added to hass.

        Show latest data after startup.
        """
        self._keba.add_update_listener(self.update_callback)
