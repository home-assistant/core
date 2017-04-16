"""
Support for the Automatic platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.automatic/
"""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA, ATTR_ATTRIBUTES)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

REQUIREMENTS = ['aioautomatic==0.1.1']

_LOGGER = logging.getLogger(__name__)

CONF_CLIENT_ID = 'client_id'
CONF_SECRET = 'secret'
CONF_DEVICES = 'devices'

DEFAULT_TIMEOUT = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CLIENT_ID): cv.string,
    vol.Required(CONF_SECRET): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_DEVICES, default=None): vol.All(
        cv.ensure_list, [cv.string])
})


@asyncio.coroutine
def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Validate the configuration and return an Automatic scanner."""
    import aioautomatic

    client = aioautomatic.Client(
        client_id=config[CONF_CLIENT_ID],
        client_secret=config[CONF_SECRET],
        client_session=async_get_clientsession(hass),
        request_kwargs={'timeout': DEFAULT_TIMEOUT})
    try:
        session = yield from client.create_session_from_password(
            config[CONF_USERNAME], config[CONF_PASSWORD])
        data = AutomaticData(hass, session, config[CONF_DEVICES], async_see)
    except aioautomatic.exceptions.AutomaticError as err:
        _LOGGER.error(str(err))
        return False

    yield from data.update()
    return True


class AutomaticData(object):
    """A class representing an Automatic cloud service connection."""

    def __init__(self, hass, session, devices, async_see):
        """Initialize the automatic device scanner."""
        self.hass = hass
        self.devices = devices
        self.session = session
        self.async_see = async_see

        async_track_time_interval(hass, self.update, timedelta(seconds=30))

    @asyncio.coroutine
    def update(self, now=None):
        """Update the device info."""
        import aioautomatic

        _LOGGER.debug('Updating devices %s', now)

        try:
            vehicles = yield from self.session.get_vehicles()
        except aioautomatic.exceptions.AutomaticError as err:
            _LOGGER.error(str(err))
            return False

        for vehicle in vehicles:
            name = vehicle.display_name
            if name is None:
                name = ' '.join(filter(None, (
                    str(vehicle.year), vehicle.make, vehicle.model)))

            if self.devices is not None and name not in self.devices:
                continue

            self.hass.async_add_job(self.update_vehicle(vehicle, name))

    @asyncio.coroutine
    def update_vehicle(self, vehicle, name):
        """Updated the specified vehicle's data."""
        import aioautomatic

        kwargs = {
            'dev_id': vehicle.id,
            'host_name': name,
            'mac': vehicle.id,
            ATTR_ATTRIBUTES: {
                'fuel_level': vehicle.fuel_level_percent,
                }
        }

        trips = []
        try:
            # Get the most recent trip for this vehicle
            trips = yield from self.session.get_trips(
                vehicle=vehicle.id, limit=1)
        except aioautomatic.exceptions.AutomaticError as err:
            _LOGGER.error(str(err))

        if trips:
            end_location = trips[0].end_location
            kwargs['gps'] = (end_location.lat, end_location.lon)
            kwargs['gps_accuracy'] = end_location.accuracy_m

        yield from self.async_see(**kwargs)
