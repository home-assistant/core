"""Support for the Mopar vehicle sensor platform."""
from homeassistant.components.mopar import (
    DOMAIN as MOPAR_DOMAIN,
    DATA_UPDATED,
    ATTR_VEHICLE_INDEX
)
from homeassistant.const import (
    ATTR_ATTRIBUTION, LENGTH_KILOMETERS)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

ICON = 'mdi:car'


async def async_setup_platform(hass, config, add_entities,
                               discovery_info=None):
    """Set up the Mopar platform."""
    data = hass.data[MOPAR_DOMAIN]
    add_entities([MoparSensor(data, index)
                  for index, _ in enumerate(data.vehicles)], True)


class MoparSensor(Entity):
    """Mopar vehicle sensor."""

    def __init__(self, data, index):
        """Initialize the sensor."""
        self._index = index
        self._vehicle = {}
        self._vhr = {}
        self._tow_guide = {}
        self._odometer = None
        self._data = data
        self._name = self._data.get_vehicle_name(self._index)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._odometer

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            ATTR_VEHICLE_INDEX: self._index,
            ATTR_ATTRIBUTION: self._data.attribution
        }
        attributes.update(self._vehicle)
        attributes.update(self._vhr)
        attributes.update(self._tow_guide)
        return attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.hass.config.units.length_unit

    @property
    def icon(self):
        """Return the icon."""
        return ICON

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    def update(self):
        """Update device state."""
        self._vehicle = self._data.vehicles[self._index]
        self._vhr = self._data.vhrs.get(self._index, {})
        self._tow_guide = self._data.tow_guides.get(self._index, {})
        if 'odometer' in self._vhr:
            odo = float(self._vhr['odometer'])
            self._odometer = int(self.hass.config.units.length(
                odo, LENGTH_KILOMETERS))

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)
