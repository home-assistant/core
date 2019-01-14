"""
Support for Recollect Waste curbside collection pickup.

For more details about this platform, please refer to the documentation at
https://github.com/stealthhacker/python-recollect-waste
"""
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['recollect-waste==1.0.0']

ATTR_PICKUP_TYPES = 'pickup_types'
ATTR_AREA_NAME = 'area_name'
CONF_UPDATE_INTERVAL = 'update_interval'
CONF_PLACE_ID = 'place_id'
CONF_SERVICE_ID = 'service_id'
DOMAIN = 'recollect_waste'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PLACE_ID): cv.string,
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(days=1)): (
        vol.All(cv.time_period, cv.positive_timedelta)),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Recollect Waste platform."""
    add_entities([RecollectWasteSensor(
        config.get(CONF_NAME),
        config.get(CONF_PLACE_ID),
        config.get(CONF_SERVICE_ID),
        config.get(CONF_UPDATE_INTERVAL))])


class RecollectWasteSensor(Entity):
    """Recollect Waste Sensor."""

    def __init__(self, name, place_id, service_id, interval):
        """Initialize the sensor."""
        self._name = name
        self.place_id = place_id
        self.service_id = service_id
        self._attributes = {}
        self._state = None
        self.update = Throttle(interval)(self._update)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name or DOMAIN

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return

    def _update(self):
        """Update device state."""
        import recollect_waste

        # pylint:disable=E1101
        client = recollect_waste.RecollectWasteClient(self.place_id,
                                                      self.service_id)
        pickup_event = client.get_next_pickup()
        self._state = pickup_event.event_date
        self._attributes[ATTR_PICKUP_TYPES] = pickup_event.pickup_types
        self._attributes[ATTR_AREA_NAME] = pickup_event.area_name
