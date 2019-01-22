"""
Support for Recollect Waste curbside collection pickup.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/components/sensor.recollect_waste/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['recollect-waste==1.0.1']

_LOGGER = logging.getLogger(__name__)
ATTR_PICKUP_TYPES = 'pickup_types'
ATTR_AREA_NAME = 'area_name'
CONF_PLACE_ID = 'place_id'
CONF_SERVICE_ID = 'service_id'
CONF_UPDATE_INTERVAL = 'update_interval'
DEFAULT_SCAN_INTERVAL = timedelta(seconds=86400)
DOMAIN = 'recollect_waste'
ICON = 'mdi:trash-can-outline'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PLACE_ID): cv.string,
    vol.Required(CONF_SERVICE_ID): cv.string,
    vol.Optional(CONF_NAME, default=DOMAIN): cv.string,
    vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_SCAN_INTERVAL): (
        vol.All(cv.time_period, cv.positive_timedelta))
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Recollect Waste platform."""
    add_entities([RecollectWasteSensor(
        config.get(CONF_NAME),
        config[CONF_PLACE_ID],
        config[CONF_SERVICE_ID],
        config.get(CONF_UPDATE_INTERVAL))], True)


class RecollectWasteSensor(Entity):
    """Recollect Waste Sensor."""

    def __init__(self, name, place_id, service_id, interval):
        """Initialize the sensor."""
        self._attributes = {}
        self._name = name
        self._state = None
        self._unique_id = "{}{}".format(place_id, service_id)
        self.place_id = place_id
        self.service_id = service_id
        self.update = Throttle(interval)(self._update)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

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
        return ICON

    def _update(self):
        """Update device state."""
        import recollect_waste

        try:
            # pylint: disable=no-member
            client = recollect_waste.RecollectWasteClient(self.place_id,
                                                          self.service_id)
            pickup_event = client.get_next_pickup()
            self._state = pickup_event.event_date
            self._attributes.update({
                ATTR_PICKUP_TYPES: pickup_event.pickup_types,
                ATTR_AREA_NAME: pickup_event.area_name
            })
        except recollect_waste.RecollectWasteException as ex:
            _LOGGER.error('Recollect Waste platform error. %s', ex)
