"""Integration with the Rachio Iro sprinkler system controller."""
import asyncio
import logging
from typing import Optional

from aiohttp import web
import voluptuous as vol
from homeassistant.auth.util import generate_secret
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_API_KEY, EVENT_HOMEASSISTANT_STOP, URL_API
from homeassistant.helpers import discovery, config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'rachio'

SUPPORTED_DOMAINS = ['switch', 'binary_sensor']

# Manual run length
CONF_MANUAL_RUN_MINS = 'manual_run_mins'
DEFAULT_MANUAL_RUN_MINS = 10
CONF_CUSTOM_URL = 'hass_url_override'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_CUSTOM_URL): cv.string,
        vol.Optional(CONF_MANUAL_RUN_MINS, default=DEFAULT_MANUAL_RUN_MINS):
            cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)

# Keys used in the API JSON
KEY_DEVICE_ID = 'deviceId'
KEY_DEVICES = 'devices'
KEY_ENABLED = 'enabled'
KEY_EXTERNAL_ID = 'externalId'
KEY_ID = 'id'
KEY_NAME = 'name'
KEY_ON = 'on'
KEY_STATUS = 'status'
KEY_SUBTYPE = 'subType'
KEY_SUMMARY = 'summary'
KEY_TYPE = 'type'
KEY_URL = 'url'
KEY_USERNAME = 'username'
KEY_ZONE_ID = 'zoneId'
KEY_ZONE_NUMBER = 'zoneNumber'
KEY_ZONES = 'zones'

STATUS_ONLINE = 'ONLINE'
STATUS_OFFLINE = 'OFFLINE'

# Device webhook values
TYPE_CONTROLLER_STATUS = 'DEVICE_STATUS'
SUBTYPE_OFFLINE = 'OFFLINE'
SUBTYPE_ONLINE = 'ONLINE'
SUBTYPE_OFFLINE_NOTIFICATION = 'OFFLINE_NOTIFICATION'
SUBTYPE_COLD_REBOOT = 'COLD_REBOOT'
SUBTYPE_SLEEP_MODE_ON = 'SLEEP_MODE_ON'
SUBTYPE_SLEEP_MODE_OFF = 'SLEEP_MODE_OFF'
SUBTYPE_BROWNOUT_VALVE = 'BROWNOUT_VALVE'
SUBTYPE_RAIN_SENSOR_DETECTION_ON = 'RAIN_SENSOR_DETECTION_ON'
SUBTYPE_RAIN_SENSOR_DETECTION_OFF = 'RAIN_SENSOR_DETECTION_OFF'
SUBTYPE_RAIN_DELAY_ON = 'RAIN_DELAY_ON'
SUBTYPE_RAIN_DELAY_OFF = 'RAIN_DELAY_OFF'

# Schedule webhook values
TYPE_SCHEDULE_STATUS = 'SCHEDULE_STATUS'
SUBTYPE_SCHEDULE_STARTED = 'SCHEDULE_STARTED'
SUBTYPE_SCHEDULE_STOPPED = 'SCHEDULE_STOPPED'
SUBTYPE_SCHEDULE_COMPLETED = 'SCHEDULE_COMPLETED'
SUBTYPE_WEATHER_NO_SKIP = 'WEATHER_INTELLIGENCE_NO_SKIP'
SUBTYPE_WEATHER_SKIP = 'WEATHER_INTELLIGENCE_SKIP'
SUBTYPE_WEATHER_CLIMATE_SKIP = 'WEATHER_INTELLIGENCE_CLIMATE_SKIP'
SUBTYPE_WEATHER_FREEZE = 'WEATHER_INTELLIGENCE_FREEZE'

# Zone webhook values
TYPE_ZONE_STATUS = 'ZONE_STATUS'
SUBTYPE_ZONE_STARTED = 'ZONE_STARTED'
SUBTYPE_ZONE_STOPPED = 'ZONE_STOPPED'
SUBTYPE_ZONE_COMPLETED = 'ZONE_COMPLETED'
SUBTYPE_ZONE_CYCLING = 'ZONE_CYCLING'
SUBTYPE_ZONE_CYCLING_COMPLETED = 'ZONE_CYCLING_COMPLETED'

# Webhook callbacks
LISTEN_EVENT_TYPES = ['DEVICE_STATUS_EVENT', 'ZONE_STATUS_EVENT']
WEBHOOK_CONST_ID = 'homeassistant.rachio:'
WEBHOOK_PATH = URL_API + DOMAIN
SIGNAL_RACHIO_UPDATE = DOMAIN + '_update'
SIGNAL_RACHIO_CONTROLLER_UPDATE = SIGNAL_RACHIO_UPDATE + '_controller'
SIGNAL_RACHIO_ZONE_UPDATE = SIGNAL_RACHIO_UPDATE + '_zone'
SIGNAL_RACHIO_SCHEDULE_UPDATE = SIGNAL_RACHIO_UPDATE + '_schedule'


def setup(hass, config) -> bool:
    """Set up the Rachio component."""
    from rachiopy import Rachio

    # Listen for incoming webhook connections
    hass.http.register_view(RachioWebhookView())

    # Configure API
    api_key = config[DOMAIN].get(CONF_API_KEY)
    rachio = Rachio(api_key)

    # Get the URL of this server
    custom_url = config[DOMAIN].get(CONF_CUSTOM_URL)
    hass_url = hass.config.api.base_url if custom_url is None else custom_url
    rachio.webhook_auth = generate_secret()
    rachio.webhook_url = hass_url + WEBHOOK_PATH

    # Get the API user
    try:
        person = RachioPerson(hass, rachio, config[DOMAIN])
    except AssertionError as error:
        _LOGGER.error("Could not reach the Rachio API: %s", error)
        return False

    # Check for Rachio controller devices
    if not person.controllers:
        _LOGGER.error("No Rachio devices found in account %s",
                      person.username)
        return False
    _LOGGER.info("%d Rachio device(s) found", len(person.controllers))

    # Enable component
    hass.data[DOMAIN] = person

    # Load platforms
    for component in SUPPORTED_DOMAINS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class RachioPerson:
    """Represent a Rachio user."""

    def __init__(self, hass, rachio, config):
        """Create an object from the provided API instance."""
        # Use API token to get user ID
        self._hass = hass
        self.rachio = rachio
        self.config = config

        response = rachio.person.getInfo()
        assert int(response[0][KEY_STATUS]) == 200, "API key error"
        self._id = response[1][KEY_ID]

        # Use user ID to get user data
        data = rachio.person.get(self._id)
        assert int(data[0][KEY_STATUS]) == 200, "User ID error"
        self.username = data[1][KEY_USERNAME]
        self._controllers = [RachioIro(self._hass, self.rachio, controller)
                             for controller in data[1][KEY_DEVICES]]
        _LOGGER.info('Using Rachio API as user "%s"', self.username)

    @property
    def user_id(self) -> str:
        """Get the user ID as defined by the Rachio API."""
        return self._id

    @property
    def controllers(self) -> list:
        """Get a list of controllers managed by this account."""
        return self._controllers


class RachioIro:
    """Represent a Rachio Iro."""

    def __init__(self, hass, rachio, data):
        """Initialize a Rachio device."""
        self.hass = hass
        self.rachio = rachio
        self._id = data[KEY_ID]
        self._name = data[KEY_NAME]
        self._zones = data[KEY_ZONES]
        self._init_data = data
        _LOGGER.debug('%s has ID "%s"', str(self), self.controller_id)

        # Listen for all updates
        self._init_webhooks()

    def _init_webhooks(self) -> None:
        """Start getting updates from the Rachio API."""
        current_webhook_id = None

        # First delete any old webhooks that may have stuck around
        def _deinit_webhooks(event) -> None:
            """Stop getting updates from the Rachio API."""
            webhooks = self.rachio.notification.getDeviceWebhook(
                self.controller_id)[1]
            for webhook in webhooks:
                if webhook[KEY_EXTERNAL_ID].startswith(WEBHOOK_CONST_ID) or\
                        webhook[KEY_ID] == current_webhook_id:
                    self.rachio.notification.deleteWebhook(webhook[KEY_ID])
        _deinit_webhooks(None)

        # Choose which events to listen for and get their IDs
        event_types = []
        for event_type in self.rachio.notification.getWebhookEventType()[1]:
            if event_type[KEY_NAME] in LISTEN_EVENT_TYPES:
                event_types.append({"id": event_type[KEY_ID]})

        # Register to listen to these events from the device
        url = self.rachio.webhook_url
        auth = WEBHOOK_CONST_ID + self.rachio.webhook_auth
        new_webhook = self.rachio.notification.postWebhook(self.controller_id,
                                                           auth, url,
                                                           event_types)
        # Save ID for deletion at shutdown
        current_webhook_id = new_webhook[1][KEY_ID]
        self.hass.bus.listen(EVENT_HOMEASSISTANT_STOP, _deinit_webhooks)

    def __str__(self) -> str:
        """Display the controller as a string."""
        return 'Rachio controller "{}"'.format(self.name)

    @property
    def controller_id(self) -> str:
        """Return the Rachio API controller ID."""
        return self._id

    @property
    def name(self) -> str:
        """Return the user-defined name of the controller."""
        return self._name

    @property
    def current_schedule(self) -> str:
        """Return the schedule that the device is running right now."""
        return self.rachio.device.getCurrentSchedule(self.controller_id)[1]

    @property
    def init_data(self) -> dict:
        """Return the information used to set up the controller."""
        return self._init_data

    def list_zones(self, include_disabled=False) -> list:
        """Return a list of the zone dicts connected to the device."""
        # All zones
        if include_disabled:
            return self._zones

        # Only enabled zones
        return [z for z in self._zones if z[KEY_ENABLED]]

    def get_zone(self, zone_id) -> Optional[dict]:
        """Return the zone with the given ID."""
        for zone in self.list_zones(include_disabled=True):
            if zone[KEY_ID] == zone_id:
                return zone

        return None

    def stop_watering(self) -> None:
        """Stop watering all zones connected to this controller."""
        self.rachio.device.stopWater(self.controller_id)
        _LOGGER.info("Stopped watering of all zones on %s", str(self))


class RachioWebhookView(HomeAssistantView):
    """Provide a page for the server to call."""

    SIGNALS = {
        TYPE_CONTROLLER_STATUS: SIGNAL_RACHIO_CONTROLLER_UPDATE,
        TYPE_SCHEDULE_STATUS: SIGNAL_RACHIO_SCHEDULE_UPDATE,
        TYPE_ZONE_STATUS: SIGNAL_RACHIO_ZONE_UPDATE,
    }

    requires_auth = False  # Handled separately
    url = WEBHOOK_PATH
    name = url[1:].replace('/', ':')

    # pylint: disable=no-self-use
    @asyncio.coroutine
    async def post(self, request) -> web.Response:
        """Handle webhook calls from the server."""
        hass = request.app['hass']
        data = await request.json()

        try:
            auth = data.get(KEY_EXTERNAL_ID, str()).split(':')[1]
            assert auth == hass.data[DOMAIN].rachio.webhook_auth
        except (AssertionError, IndexError):
            return web.Response(status=web.HTTPForbidden.status_code)

        update_type = data[KEY_TYPE]
        if update_type in self.SIGNALS:
            async_dispatcher_send(hass, self.SIGNALS[update_type], data)

        return web.Response(status=web.HTTPNoContent.status_code)
