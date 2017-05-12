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
    PLATFORM_SCHEMA, ATTR_ATTRIBUTES, ATTR_DEV_ID, ATTR_HOST_NAME, ATTR_MAC,
    ATTR_GPS, ATTR_GPS_ACCURACY)
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP,
    EVENT_HOMEASSISTANT_START)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

REQUIREMENTS = ['aioautomatic==0.4.0']

_LOGGER = logging.getLogger(__name__)

CONF_CLIENT_ID = 'client_id'
CONF_SECRET = 'secret'
CONF_DEVICES = 'devices'

DEFAULT_TIMEOUT = 5

DEFAULT_SCOPE = ['location', 'vehicle:profile', 'trip']
FULL_SCOPE = DEFAULT_SCOPE + ['current_location']

ATTR_FUEL_LEVEL = 'fuel_level'

EVENT_AUTOMATIC_UPDATE = 'automatic_update'

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
        try:
            session = yield from client.create_session_from_password(
                FULL_SCOPE, config[CONF_USERNAME], config[CONF_PASSWORD])
        except aioautomatic.exceptions.ForbiddenError as exc:
            if not str(exc).startswith("invalid_scope"):
                raise exc
            _LOGGER.info("Client not authorized for current_location scope. "
                         "location:updated events will not be received.")
            session = yield from client.create_session_from_password(
                DEFAULT_SCOPE, config[CONF_USERNAME], config[CONF_PASSWORD])

        data = AutomaticData(
            hass, client, session, config[CONF_DEVICES], async_see)

        # Load the initial vehicle data
        vehicles = yield from session.get_vehicles()
        for vehicle in vehicles:
            hass.async_add_job(data.load_vehicle(vehicle))
    except aioautomatic.exceptions.AutomaticError as err:
        _LOGGER.error(str(err))
        return False

    @callback
    def ws_connect(event):
        """Open the websocket connection."""
        hass.async_add_job(data.ws_connect())

    @callback
    def ws_close(event):
        """Close the websocket connection."""
        hass.async_add_job(data.ws_close())

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, ws_connect)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, ws_close)

    return True


class AutomaticData(object):
    """A class representing an Automatic cloud service connection."""

    def __init__(self, hass, client, session, devices, async_see):
        """Initialize the automatic device scanner."""
        self.hass = hass
        self.devices = devices
        self.vehicle_info = {}
        self.client = client
        self.session = session
        self.async_see = async_see
        self.ws_reconnect_handle = None
        self.ws_close_requested = False

        self.client.on_app_event(
            lambda name, event: self.hass.async_add_job(
                self.handle_event(name, event)))

    @asyncio.coroutine
    def handle_event(self, name, event):
        """Coroutine to update state for a realtime event."""
        import aioautomatic

        # Fire a hass event
        self.hass.bus.async_fire(EVENT_AUTOMATIC_UPDATE, event.data)

        if event.vehicle.id not in self.vehicle_info:
            # If vehicle hasn't been seen yet, request the detailed
            # info for this vehicle.
            _LOGGER.info("New vehicle found.")
            try:
                vehicle = yield from event.get_vehicle()
            except aioautomatic.exceptions.AutomaticError as err:
                _LOGGER.error(str(err))
                return
            yield from self.get_vehicle_info(vehicle)

        kwargs = self.vehicle_info[event.vehicle.id]
        if kwargs is None:
            # Ignored device
            return

        # If this is a vehicle status report, update the fuel level
        if name == "vehicle:status_report":
            fuel_level = event.vehicle.fuel_level_percent
            if fuel_level is not None:
                kwargs[ATTR_ATTRIBUTES][ATTR_FUEL_LEVEL] = fuel_level

        # Send the device seen notification
        if event.location is not None:
            kwargs[ATTR_GPS] = (event.location.lat, event.location.lon)
            kwargs[ATTR_GPS_ACCURACY] = event.location.accuracy_m

        yield from self.async_see(**kwargs)

    @asyncio.coroutine
    def ws_connect(self, now=None):
        """Open the websocket connection."""
        import aioautomatic
        self.ws_close_requested = False

        if self.ws_reconnect_handle is not None:
            _LOGGER.debug("Retrying websocket connection.")
        try:
            ws_loop_future = yield from self.client.ws_connect()
        except aioautomatic.exceptions.UnauthorizedClientError:
            _LOGGER.error("Client unauthorized for websocket connection. "
                          "Ensure Websocket is selected in the Automatic "
                          "developer application event delivery preferences.")
            return
        except aioautomatic.exceptions.AutomaticError as err:
            if self.ws_reconnect_handle is None:
                # Show log error and retry connection every 5 minutes
                _LOGGER.error("Error opening websocket connection: %s", err)
                self.ws_reconnect_handle = async_track_time_interval(
                    self.hass, self.ws_connect, timedelta(minutes=5))
            return

        if self.ws_reconnect_handle is not None:
            self.ws_reconnect_handle()
            self.ws_reconnect_handle = None

        _LOGGER.info("Websocket connected.")

        try:
            yield from ws_loop_future
        except aioautomatic.exceptions.AutomaticError as err:
            _LOGGER.error(str(err))

        _LOGGER.info("Websocket closed.")

        # If websocket was close was not requested, attempt to reconnect
        if not self.ws_close_requested:
            self.hass.loop.create_task(self.ws_connect())

    @asyncio.coroutine
    def ws_close(self):
        """Close the websocket connection."""
        self.ws_close_requested = True
        if self.ws_reconnect_handle is not None:
            self.ws_reconnect_handle()
            self.ws_reconnect_handle = None

        yield from self.client.ws_close()

    @asyncio.coroutine
    def load_vehicle(self, vehicle):
        """Load the vehicle's initial state and update hass."""
        kwargs = yield from self.get_vehicle_info(vehicle)
        yield from self.async_see(**kwargs)

    @asyncio.coroutine
    def get_vehicle_info(self, vehicle):
        """Fetch the latest vehicle info from automatic."""
        import aioautomatic

        name = vehicle.display_name
        if name is None:
            name = ' '.join(filter(None, (
                str(vehicle.year), vehicle.make, vehicle.model)))

        if self.devices is not None and name not in self.devices:
            self.vehicle_info[vehicle.id] = None
            return
        else:
            self.vehicle_info[vehicle.id] = kwargs = {
                ATTR_DEV_ID: vehicle.id,
                ATTR_HOST_NAME: name,
                ATTR_MAC: vehicle.id,
                ATTR_ATTRIBUTES: {
                    ATTR_FUEL_LEVEL: vehicle.fuel_level_percent,
                }
            }

        if vehicle.latest_location is not None:
            location = vehicle.latest_location
            kwargs[ATTR_GPS] = (location.lat, location.lon)
            kwargs[ATTR_GPS_ACCURACY] = location.accuracy_m
            return kwargs

        trips = []
        try:
            # Get the most recent trip for this vehicle
            trips = yield from self.session.get_trips(
                vehicle=vehicle.id, limit=1)
        except aioautomatic.exceptions.AutomaticError as err:
            _LOGGER.error(str(err))

        if trips:
            location = trips[0].end_location
            kwargs[ATTR_GPS] = (location.lat, location.lon)
            kwargs[ATTR_GPS_ACCURACY] = location.accuracy_m

        return kwargs
