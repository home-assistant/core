"""
Support for DoorBird device.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/doorbird/
"""
import logging

import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_HOST, CONF_USERNAME, \
    CONF_PASSWORD, CONF_NAME, CONF_DEVICES, CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify

REQUIREMENTS = ['doorbirdpy==2.0.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'doorbird'

API_URL = '/api/{}'.format(DOMAIN)

CONF_CUSTOM_URL = 'hass_url_override'
CONF_DOORBELL_EVENTS = 'doorbell_events'
CONF_DOORBELL_NUMS = 'doorbell_numbers'
CONF_MOTION_EVENTS = 'motion_events'
CONF_TOKEN = 'token'

SENSOR_TYPES = {
    'doorbell': {
        'name': 'Button',
        'device_class': 'occupancy',
    },
    'motion': {
        'name': 'Motion',
        'device_class': 'motion',
    },
}

RESET_DEVICE_FAVORITES = 'doorbird_reset_favorites'

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_DOORBELL_NUMS, default=[1]): vol.All(
        cv.ensure_list, [cv.positive_int]),
    vol.Optional(CONF_CUSTOM_URL): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [DEVICE_SCHEMA])
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the DoorBird component."""
    from doorbirdpy import DoorBird

    token = config[DOMAIN].get(CONF_TOKEN)

    # Provide an endpoint for the doorstations to call to trigger events
    hass.http.register_view(DoorBirdRequestView(token))

    # Provide an endpoint for the user to call to clear device changes
    hass.http.register_view(DoorBirdCleanupView(token))

    doorstations = []

    for index, doorstation_config in enumerate(config[DOMAIN][CONF_DEVICES]):
        device_ip = doorstation_config.get(CONF_HOST)
        username = doorstation_config.get(CONF_USERNAME)
        password = doorstation_config.get(CONF_PASSWORD)
        doorbell_nums = doorstation_config.get(CONF_DOORBELL_NUMS)
        custom_url = doorstation_config.get(CONF_CUSTOM_URL)
        events = doorstation_config.get(CONF_MONITORED_CONDITIONS)
        name = (doorstation_config.get(CONF_NAME)
                or 'DoorBird {}'.format(index + 1))

        device = DoorBird(device_ip, username, password)
        status = device.ready()

        if status[0]:
            doorstation = ConfiguredDoorBird(device, name, events, custom_url,
                                             doorbell_nums, token)
            doorstations.append(doorstation)
            _LOGGER.info('Connected to DoorBird "%s" as %s@%s',
                         doorstation.name, username, device_ip)
        elif status[1] == 401:
            _LOGGER.error("Authorization rejected by DoorBird for %s@%s",
                          username, device_ip)
            return False
        else:
            _LOGGER.error("Could not connect to DoorBird as %s@%s: Error %s",
                          username, device_ip, str(status[1]))
            return False

        # Subscribe to doorbell or motion events
        if events is not None:
            doorstation.update_schedule(hass)

    hass.data[DOMAIN] = doorstations

    def _reset_device_favorites_handler(event):
        """Handle clearing favorites on device."""
        slug = event.data.get('slug')

        if slug is None:
            return

        doorstation = get_doorstation_by_slug(hass, slug)

        if doorstation is None:
            _LOGGER.error('Device not found %s', format(slug))

        # Clear webhooks
        favorites = doorstation.device.favorites()

        for favorite_type in favorites:
            for favorite_id in favorites[favorite_type]:
                doorstation.device.delete_favorite(favorite_type, favorite_id)

    hass.bus.listen(RESET_DEVICE_FAVORITES, _reset_device_favorites_handler)

    return True


def get_doorstation_by_slug(hass, slug):
    """Get doorstation by slug."""
    for doorstation in hass.data[DOMAIN]:
        if slugify(doorstation.name) in slug:
            return doorstation


def handle_event(event):
    """Handle dummy events."""
    return None


class ConfiguredDoorBird():
    """Attach additional information to pass along with configured device."""

    def __init__(self, device, name, events, custom_url, doorbell_nums, token):
        """Initialize configured device."""
        self._name = name
        self._device = device
        self._custom_url = custom_url
        self._monitored_events = events
        self._doorbell_nums = doorbell_nums
        self._token = token

    @property
    def name(self):
        """Get custom device name."""
        return self._name

    @property
    def device(self):
        """Get the configured device."""
        return self._device

    @property
    def custom_url(self):
        """Get custom url for device."""
        return self._custom_url

    def update_schedule(self, hass):
        """Register monitored sensors and deregister others."""
        from doorbirdpy import DoorBirdScheduleEntrySchedule

        # Create a new schedule (24/7)
        schedule = DoorBirdScheduleEntrySchedule()
        schedule.add_weekday(0, 604800)  # seconds in a week

        # Get the URL of this server
        hass_url = hass.config.api.base_url

        # Override url if another is specified in the configuration
        if self.custom_url is not None:
            hass_url = self.custom_url

        # For all sensor types (enabled + disabled)
        for sensor_type in SENSOR_TYPES:
            name = '{} {}'.format(self.name, SENSOR_TYPES[sensor_type]['name'])
            slug = slugify(name)

            url = '{}{}/{}?token={}'.format(hass_url, API_URL, slug,
                                            self._token)
            if sensor_type in self._monitored_events:
                # Enabled -> register
                self._register_event(url, sensor_type, schedule)
                _LOGGER.info('Registered for %s pushes from DoorBird "%s". '
                             'Use the "%s_%s" event for automations.',
                             sensor_type, self.name, DOMAIN, slug)

                # Register a dummy listener so event is listed in GUI
                hass.bus.listen('{}_{}'.format(DOMAIN, slug), handle_event)
            else:
                # Disabled -> deregister
                self._deregister_event(url, sensor_type)
                _LOGGER.info('Deregistered %s pushes from DoorBird "%s". '
                             'If any old favorites or schedules remain, '
                             'follow the instructions in the component '
                             'documentation to clear device registrations.',
                             sensor_type, self.name)

    def _register_event(self, hass_url, event, schedule):
        """Add a schedule entry in the device for a sensor."""
        from doorbirdpy import DoorBirdScheduleEntryOutput

        # Register HA URL as webhook if not already, then get the ID
        if not self.webhook_is_registered(hass_url):
            self.device.change_favorite('http',
                                        'Home Assistant on {} ({} events)'
                                        .format(hass_url, event), hass_url)
        fav_id = self.get_webhook_id(hass_url)

        if not fav_id:
            _LOGGER.warning('Could not find favorite for URL "%s". '
                            'Skipping sensor "%s".', hass_url, event)
            return

        # Add event handling to device schedule
        output = DoorBirdScheduleEntryOutput(event='http',
                                             param=fav_id,
                                             schedule=schedule)

        if event == 'doorbell':
            # Repeat edit for each monitored doorbell number
            for doorbell in self._doorbell_nums:
                entry = self.device.get_schedule_entry(event, str(doorbell))
                entry.output.append(output)
                self.device.change_schedule(entry)
        else:
            entry = self.device.get_schedule_entry(event)
            entry.output.append(output)
            self.device.change_schedule(entry)

    def _deregister_event(self, hass_url, event):
        """Remove the schedule entry in the device for a sensor."""
        # Find the right favorite and delete it
        fav_id = self.get_webhook_id(hass_url)
        if not fav_id:
            return

        self._device.delete_favorite('http', fav_id)

        if event == 'doorbell':
            # Delete the matching schedule for each doorbell number
            for doorbell in self._doorbell_nums:
                self._delete_schedule_action(event, fav_id, str(doorbell))
        else:
            self._delete_schedule_action(event, fav_id)

    def _delete_schedule_action(self, sensor, fav_id, param=""):
        """Remove the HA output from a schedule."""
        entries = self._device.schedule()
        for entry in entries:
            if entry.input != sensor or entry.param != param:
                continue

            for action in entry.output:
                if action.event == 'http' and action.param == fav_id:
                    entry.output.remove(action)

            self._device.change_schedule(entry)

    def webhook_is_registered(self, ha_url, favs=None) -> bool:
        """Return whether the given URL is registered as a device favorite."""
        favs = favs if favs else self.device.favorites()

        if 'http' not in favs:
            return False

        for fav in favs['http'].values():
            if fav['value'] == ha_url:
                return True

        return False

    def get_webhook_id(self, ha_url, favs=None) -> str or None:
        """
        Return the device favorite ID for the given URL.

        The favorite must exist or there will be problems.
        """
        favs = favs if favs else self.device.favorites()

        if 'http' not in favs:
            return None

        for fav_id in favs['http']:
            if favs['http'][fav_id]['value'] == ha_url:
                return fav_id

        return None


class DoorBirdRequestView(HomeAssistantView):
    """Provide a page for the device to call."""

    requires_auth = False
    url = API_URL
    name = API_URL[1:].replace('/', ':')
    extra_urls = [API_URL + '/{sensor}']

    def __init__(self, token):
        """Initialize view."""
        HomeAssistantView.__init__(self)
        self._token = token

    # pylint: disable=no-self-use
    async def get(self, request, sensor):
        """Respond to requests from the device."""
        from aiohttp import web
        hass = request.app['hass']

        request_token = request.query.get('token')

        authenticated = request_token == self._token

        if request_token == '' or not authenticated:
            return web.Response(status=401, text='Unauthorized')

        hass.bus.async_fire('{}_{}'.format(DOMAIN, sensor))

        return web.Response(status=200, text='OK')


class DoorBirdCleanupView(HomeAssistantView):
    """Provide a URL to call to delete ALL webhooks/schedules."""

    requires_auth = False
    url = API_URL + '/clear/{slug}'
    name = 'DoorBird Cleanup'

    def __init__(self, token):
        """Initialize view."""
        HomeAssistantView.__init__(self)
        self._token = token

    # pylint: disable=no-self-use
    async def get(self, request, slug):
        """Act on requests."""
        from aiohttp import web
        hass = request.app['hass']

        request_token = request.query.get('token')

        authenticated = request_token == self._token

        if request_token == '' or not authenticated:
            return web.Response(status=401, text='Unauthorized')

        device = get_doorstation_by_slug(hass, slug)

        # No matching device
        if device is None:
            return web.Response(status=404,
                                text='Device slug {} not found'.format(slug))

        hass.bus.async_fire(RESET_DEVICE_FAVORITES,
                            {'slug': slug})

        message = 'Clearing schedule for {}'.format(slug)
        return web.Response(status=200, text=message)
