"""
Support for Volvo On Call.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/volvooncall/
"""

from datetime import timedelta
import logging

from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.util.dt import utcnow
import voluptuous as vol

DOMAIN = 'volvooncall'

REQUIREMENTS = ['volvooncall==0.3.0']

_LOGGER = logging.getLogger(__name__)

CONF_UPDATE_INTERVAL = 'update_interval'
MIN_UPDATE_INTERVAL = timedelta(minutes=1)
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=1)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): (
            vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL)))
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the VOC component."""
    from volvooncall import Connection
    connection = Connection(
        config[DOMAIN].get(CONF_USERNAME),
        config[DOMAIN].get(CONF_PASSWORD))

    interval = config[DOMAIN].get(CONF_UPDATE_INTERVAL)

    class state:  # pylint:disable=invalid-name
        """Namespace to hold state for each vehicle."""

        entities = {}
        vehicles = {}

    hass.data[DOMAIN] = state

    def discover_vehicle(vehicle):
        """Load relevant platforms."""
        state.entities[vehicle.vin] = []
        components = ['sensor', 'binary_sensor']

        if getattr(vehicle, 'position'):
            components.append('device_tracker')

        if vehicle.heater_supported:
            components.append('switch')

        if vehicle.lock_supported:
            components.append('lock')

        for component in components:
            discovery.load_platform(hass,
                                    component,
                                    DOMAIN,
                                    vehicle.vin,
                                    config)

    def update_vehicle(vehicle):
        """Updated information on vehicle received."""
        state.vehicles[vehicle.vin] = vehicle
        if vehicle.vin not in state.entities:
            discover_vehicle(vehicle)

        for entity in state.entities[vehicle.vin]:
            if isinstance(entity, Entity):
                entity.schedule_update_ha_state()
            else:
                entity(vehicle)  # device tracker

    def update(now):
        """Update status from the online service."""
        try:
            if not connection.update():
                _LOGGER.warning('Could not query server')
                return False

            for vehicle in connection.vehicles:
                update_vehicle(vehicle)

            return True
        finally:
            track_point_in_utc_time(hass, update, now + interval)

    _LOGGER.info('Logging in to service')
    return update(utcnow())


class VolvoEntity(Entity):
    """Base class for all VOC entities."""

    def __init__(self, hass, vin):
        """Initialize the entity."""
        self._hass = hass
        self._vin = vin
        self._hass.data[DOMAIN].entities[self._vin].append(self)

    @property
    def vehicle(self):
        """Return vehicle."""
        return self._hass.data[DOMAIN].vehicles[self._vin]

    @property
    def name(self):
        """Return the name of the sensor."""
        return '%s %s' % (
            self.vehicle.registration_number,
            self._name)

    @property
    def _name(self):
        """Overridden by subclasses."""
        return None

    @property
    def should_poll(self):
        """Polling is not needed."""
        return False

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return dict(model='%s/%s' % (
            self.vehicle.vehicle_type,
            self.vehicle.model_year))
