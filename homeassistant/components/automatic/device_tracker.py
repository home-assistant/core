"""Support for the Automatic platform."""
import asyncio
from datetime import timedelta
import json
import logging
import os

from aiohttp import web
import voluptuous as vol

from homeassistant.components.device_tracker import (
    ATTR_ATTRIBUTES, ATTR_DEV_ID, ATTR_GPS, ATTR_GPS_ACCURACY, ATTR_HOST_NAME,
    ATTR_MAC, PLATFORM_SCHEMA)
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

ATTR_FUEL_LEVEL = 'fuel_level'
AUTOMATIC_CONFIG_FILE = '.automatic/session-{}.json'

CONF_CLIENT_ID = 'client_id'
CONF_CURRENT_LOCATION = 'current_location'
CONF_DEVICES = 'devices'
CONF_SECRET = 'secret'

DATA_CONFIGURING = 'automatic_configurator_clients'
DATA_REFRESH_TOKEN = 'refresh_token'
DEFAULT_SCOPE = ['location', 'trip', 'vehicle:events', 'vehicle:profile']
DEFAULT_TIMEOUT = 5
EVENT_AUTOMATIC_UPDATE = 'automatic_update'

FULL_SCOPE = DEFAULT_SCOPE + ['current_location']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CLIENT_ID): cv.string,
    vol.Required(CONF_SECRET): cv.string,
    vol.Optional(CONF_CURRENT_LOCATION, default=False): cv.boolean,
    vol.Optional(CONF_DEVICES): vol.All(cv.ensure_list, [cv.string]),
})


def _get_refresh_token_from_file(hass, filename):
    """Attempt to load session data from file."""
    path = hass.config.path(filename)

    if not os.path.isfile(path):
        return None

    try:
        with open(path) as data_file:
            data = json.load(data_file)
            if data is None:
                return None

            return data.get(DATA_REFRESH_TOKEN)
    except ValueError:
        return None


def _write_refresh_token_to_file(hass, filename, refresh_token):
    """Attempt to store session data to file."""
    path = hass.config.path(filename)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w+') as data_file:
        json.dump({
            DATA_REFRESH_TOKEN: refresh_token
        }, data_file)


@asyncio.coroutine
def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Validate the configuration and return an Automatic scanner."""
    import aioautomatic

    hass.http.register_view(AutomaticAuthCallbackView())

    scope = FULL_SCOPE if config.get(CONF_CURRENT_LOCATION) else DEFAULT_SCOPE

    client = aioautomatic.Client(
        client_id=config[CONF_CLIENT_ID],
        client_secret=config[CONF_SECRET],
        client_session=async_get_clientsession(hass),
        request_kwargs={'timeout': DEFAULT_TIMEOUT})

    filename = AUTOMATIC_CONFIG_FILE.format(config[CONF_CLIENT_ID])
    refresh_token = yield from hass.async_add_job(
        _get_refresh_token_from_file, hass, filename)

    @asyncio.coroutine
    def initialize_data(session):
        """Initialize the AutomaticData object from the created session."""
        hass.async_add_job(
            _write_refresh_token_to_file, hass, filename,
            session.refresh_token)
        data = AutomaticData(
            hass, client, session, config.get(CONF_DEVICES), async_see)

        # Load the initial vehicle data
        vehicles = yield from session.get_vehicles()
        for vehicle in vehicles:
            hass.async_create_task(data.load_vehicle(vehicle))

        # Create a task instead of adding a tracking job, since this task will
        # run until the websocket connection is closed.
        hass.loop.create_task(data.ws_connect())

    if refresh_token is not None:
        try:
            session = yield from client.create_session_from_refresh_token(
                refresh_token)
            yield from initialize_data(session)
            return True
        except aioautomatic.exceptions.AutomaticError as err:
            _LOGGER.error(str(err))

    configurator = hass.components.configurator
    request_id = configurator.async_request_config(
        "Automatic", description=(
            "Authorization required for Automatic device tracker."),
        link_name="Click here to authorize Home Assistant.",
        link_url=client.generate_oauth_url(scope),
        entity_picture="/static/images/logo_automatic.png",
    )

    @asyncio.coroutine
    def initialize_callback(code, state):
        """Call after OAuth2 response is returned."""
        try:
            session = yield from client.create_session_from_oauth_code(
                code, state)
            yield from initialize_data(session)
            configurator.async_request_done(request_id)
        except aioautomatic.exceptions.AutomaticError as err:
            _LOGGER.error(str(err))
            configurator.async_notify_errors(request_id, str(err))
            return False

    if DATA_CONFIGURING not in hass.data:
        hass.data[DATA_CONFIGURING] = {}

    hass.data[DATA_CONFIGURING][client.state] = initialize_callback
    return True


class AutomaticAuthCallbackView(HomeAssistantView):
    """Handle OAuth finish callback requests."""

    requires_auth = False
    url = '/api/automatic/callback'
    name = 'api:automatic:callback'

    @callback
    def get(self, request):  # pylint: disable=no-self-use
        """Finish OAuth callback request."""
        hass = request.app['hass']
        params = request.query
        response = web.HTTPFound('/states')

        if 'state' not in params or 'code' not in params:
            if 'error' in params:
                _LOGGER.error(
                    "Error authorizing Automatic: %s", params['error'])
                return response
            _LOGGER.error(
                "Error authorizing Automatic. Invalid response returned")
            return response

        if DATA_CONFIGURING not in hass.data or \
                params['state'] not in hass.data[DATA_CONFIGURING]:
            _LOGGER.error("Automatic configuration request not found")
            return response

        code = params['code']
        state = params['state']
        initialize_callback = hass.data[DATA_CONFIGURING][state]
        hass.async_create_task(initialize_callback(code, state))

        return response


class AutomaticData:
    """A class representing an Automatic cloud service connection."""

    def __init__(self, hass, client, session, devices, async_see):
        """Initialize the automatic device scanner."""
        self.hass = hass
        self.devices = devices
        self.vehicle_info = {}
        self.vehicle_seen = {}
        self.client = client
        self.session = session
        self.async_see = async_see
        self.ws_reconnect_handle = None
        self.ws_close_requested = False

        self.client.on_app_event(
            lambda name, event: self.hass.async_create_task(
                self.handle_event(name, event)))

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.ws_close())

    @asyncio.coroutine
    def handle_event(self, name, event):
        """Coroutine to update state for a real time event."""
        import aioautomatic

        self.hass.bus.async_fire(EVENT_AUTOMATIC_UPDATE, event.data)

        if event.vehicle.id not in self.vehicle_info:
            # If vehicle hasn't been seen yet, request the detailed
            # info for this vehicle.
            _LOGGER.info("New vehicle found")
            try:
                vehicle = yield from event.get_vehicle()
            except aioautomatic.exceptions.AutomaticError as err:
                _LOGGER.error(str(err))
                return
            yield from self.get_vehicle_info(vehicle)

        if event.created_at < self.vehicle_seen[event.vehicle.id]:
            # Skip events received out of order
            _LOGGER.debug("Skipping out of order event. Event Created %s. "
                          "Last seen event: %s", event.created_at,
                          self.vehicle_seen[event.vehicle.id])
            return
        self.vehicle_seen[event.vehicle.id] = event.created_at

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
            _LOGGER.debug("Retrying websocket connection")
        try:
            ws_loop_future = yield from self.client.ws_connect()
        except aioautomatic.exceptions.UnauthorizedClientError:
            _LOGGER.error("Client unauthorized for websocket connection. "
                          "Ensure Websocket is selected in the Automatic "
                          "developer application event delivery preferences")
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

        _LOGGER.info("Websocket connected")

        try:
            yield from ws_loop_future
        except aioautomatic.exceptions.AutomaticError as err:
            _LOGGER.error(str(err))

        _LOGGER.info("Websocket closed")

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

        self.vehicle_info[vehicle.id] = kwargs = {
            ATTR_DEV_ID: vehicle.id,
            ATTR_HOST_NAME: name,
            ATTR_MAC: vehicle.id,
            ATTR_ATTRIBUTES: {
                ATTR_FUEL_LEVEL: vehicle.fuel_level_percent,
            }
        }
        self.vehicle_seen[vehicle.id] = \
            vehicle.updated_at or vehicle.created_at

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

            if trips[0].ended_at >= self.vehicle_seen[vehicle.id]:
                self.vehicle_seen[vehicle.id] = trips[0].ended_at

        return kwargs
