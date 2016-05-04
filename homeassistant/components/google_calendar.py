"""
Support for custom shell commands to to retrieve values.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.command/
"""
# pylint: disable=import-error
import logging
from datetime import timedelta
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant import bootstrap
from homeassistant.const import (
    ATTR_DISCOVERED, ATTR_SERVICE, EVENT_PLATFORM_DISCOVERED)

REQUIREMENTS = [
    'google-api-python-client',
]
DEPENDENCIES = ['http']

_LOGGER = logging.getLogger(__name__)
_CONFIGURING = {}

DOMAIN = 'google_calendar'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_FQDN = 'fqdn'
CONF_TRACK_NEW = 'track_new_calendar'
CONF_SCAN_INTERVAL = 'scan_interval'
CONF_CAL_ID = 'cal_id'
CONF_NAME = 'name'
CONF_ENTITIES = 'entities'
CONF_TRACK = 'track'
CONF_SEARCH = 'search'
CONF_OFFSET = 'offset'

DEFAULT_CONF_TRACK_NEW = True
DEFAULT_CONF_SCAN_INTERVAL = 60
DEFAULT_CONF_OFFSET = '#-'

DEFAULT_GOOGLE_SEARCH_PARAMS = {
    'orderBy': 'startTime',
    'maxResults': 1,
    'singleEvents': True,
}

GROUP_NAME_ALL_CALENDARS = "Google Calendar Sensors"

DISCOVER_BINARY_SENSORS = '{}.binary_sensor'.format(DOMAIN)
SERVICE_SCAN_CALENDARS = 'scan_for_calendars'

YAML_DEVICES = '{}_devices.yaml'.format(DOMAIN)
SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CONFIG_FILE = '{}.conf'.format(DOMAIN)
TOKEN_FILE = '.{}.token'.format(DOMAIN)
CAL_SEARCH_START = '/auth/{}'.format(DOMAIN)
CAL_SEARCH_CALLBACK = '/auth/{}/callback'.format(DOMAIN)

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

PLATFORM_SCHEMA = vol.Schema({
    vol.Optional(CONF_FQDN): cv.string,
    vol.Optional(CONF_TRACK_NEW): cv.boolean,
    vol.Optional(CONF_SCAN_INTERVAL): cv.positive_int,
})

_SINGLE_CALSEARCH_CONFIG = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_TRACK): cv.boolean,
    vol.Optional(CONF_SEARCH): vol.Any(cv.string, None),
    vol.Optional(CONF_OFFSET): cv.string,
})

_CALENDARS = {}
_OAUTH_PATH_SETUP = False


def get_fqdn():
    """Get system fqdn or None."""
    import socket
    from homeassistant.util import get_local_ip
    hostname = 'PLEASE_SET_FQDN_IN_CONFIGURATION'
    try:
        hostname = socket.gethostbyaddr(get_local_ip())[0]
    except socket.gaierror:
        _LOGGER.error('Unable to get the hostname automatically, ' +
                      'you need to set %s in the configuration',
                      CONF_FQDN)
    return hostname


def _calsearch_dict(value):
    """Validate a dictionary of group definitions."""
    config = []
    for calsearch in value:
        try:
            config.append(_SINGLE_CALSEARCH_CONFIG(calsearch))
        except vol.MultipleInvalid as ex:
            raise vol.Invalid('Google Calendar Entity is invalid: {}: {}'.
                              format(calsearch, ex))
    return config


DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_CAL_ID): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_ENTITIES, None): vol.All(list, _calsearch_dict),
}, extra=vol.ALLOW_EXTRA)


def setup_oauth_paths(hass, config):
    """Start setup of app with Google Oauth."""
    # pylint disable=import-error,global-statement
    base_url = "{}://{}:{}".format(
        'https' if hass.http.use_ssl else 'http',
        config.get(CONF_FQDN, get_fqdn()),
        hass.http.server_address[1])

    global _OAUTH_PATH_SETUP
    if _OAUTH_PATH_SETUP:
        return

    from homeassistant.const import HTTP_OK
    from oauth2client import client
    flow = client.flow_from_clientsecrets(
        hass.config.path(CONFIG_FILE),
        scope=SCOPES,
        redirect_uri="{}{}".format(base_url, CAL_SEARCH_CALLBACK)
    )
    # get a long term token with refresh_token
    flow.params['access_type'] = 'offline'
    flow.params['approval_prompt'] = 'force'

    def _start_auth(handler, path_match, data):
        """URL for starting Oauth session setup."""
        # pylint disable=unused-argument
        uri = flow.step1_get_authorize_url()
        handler.send_response(301)
        handler.send_header("Location", uri)
        handler.end_headers()

    def _finish_auth(handler, path_match, data):
        """Oauth callback one authenticated with Google."""
        if data.get("code") is None:
            _LOGGER.error('Unknown error when authing')
            response_message = """Something went wrong when attempting to
                                authenticate with Google!"""
        else:
            from oauth2client.file import Storage
            credentials = flow.step2_exchange(data.get("code"))
            storage = Storage(hass.config.path(TOKEN_FILE))
            storage.put(credentials)
            do_setup(hass, config)
            _LOGGER.info('Got credentials setup from Google')
            response_message = """We're all setup now"""

        html_response = """<html><head><title>Google Calendar Search</title>
                </head><body><h1>{}</h1>
                You can now close this window and restart Home-Assistant</br>
                Restarting is not essential it will just cleanup the
                </body>
                </html>""".format(response_message)
        html_response = html_response.encode("utf-8")
        handler.send_response(HTTP_OK)
        handler.write_content(html_response, content_type="text/html")

    hass.http.register_path("GET",
                            CAL_SEARCH_START,
                            _start_auth,
                            require_auth=False)
    hass.http.register_path("GET",
                            CAL_SEARCH_CALLBACK,
                            _finish_auth,
                            require_auth=False)

    _OAUTH_PATH_SETUP = True
    return


def request_oauth_setup(hass, config):
    """Request completion of oauth setup."""
    from homeassistant.loader import get_component
    configurator = get_component('configurator')
    if DOMAIN in _CONFIGURING:
        configurator.notify_errors(_CONFIGURING[DOMAIN],
                                   "Failed to register, please try again.")
        return False

    from homeassistant.components.weblink import Link
    Link(hass, 'Authenticate Google', CAL_SEARCH_START, None)
    return


def request_api_setup(hass, config):
    """Request completion of oauth setup."""
    from homeassistant.loader import get_component
    configurator = get_component('configurator')
    if DOMAIN in _CONFIGURING:
        return False

    description = """Please setup Google API per:
        https://home-assistant.io/setup"""

    def _configuration_callback(callback_data):
        """What actions to do when user clicks button."""
        # pylint disable=unused-argument
        import os
        config_file = hass.config.path(CONFIG_FILE)
        if not os.path.isfile(config_file):
            configurator.notify_errors(_CONFIGURING[DOMAIN],
                                       """Failed to locate json file,
                                       please try again.""")
            return False
        configurator.request_done(_CONFIGURING.pop(DOMAIN))
        request_oauth_setup(hass, config)
        return True

    _CONFIGURING[DOMAIN] = configurator.request_config(
        hass,
        DOMAIN,
        _configuration_callback,
        description=description,
        submit_caption="I have created the JSON file"
    )


def do_setup_check(hass, config):
    """Verify that we have both the Google Api setup and Oauth."""
    import os

    config_file = hass.config.path(CONFIG_FILE)
    if not os.path.isfile(config_file):
        # we don't have a setup yet
        request_api_setup(hass, config)
        return False

    # check that oauth is setup
    token_file = hass.config.path(TOKEN_FILE)
    if not os.path.isfile(token_file):
        # we don't have a setup yet
        request_oauth_setup(hass, config)
        return False

    return True


def setup(hass, config):
    """Setup the platform."""
    config = dict(config)  # copy it so we can modify

    config = config.get(DOMAIN, {})
    if isinstance(config, list) and len(config) > 0:
        config = config[0]

    def _scan_for_calendars(service):
        """Scan for new calendars."""
        from homeassistant.util import convert
        track_new = convert(config.get(CONF_TRACK_NEW),
                            bool, DEFAULT_CONF_TRACK_NEW)
        service = get_calendar_service(hass)
        calendars = service.calendarList().list().execute()['items']
        for calendar in calendars:
            found_calendar(hass, calendar, track_new)

    hass.services.register(
        DOMAIN, SERVICE_SCAN_CALENDARS, _scan_for_calendars,
        None, schema=None)

    if not do_setup_check(hass, config):
        return False

    do_setup(hass, config)
    return True


def do_setup(hass, config):
    """Run the setup after we have everything configured."""
    # pylint disable=global-statement
    from homeassistant.loader import get_component

    if DOMAIN in _CONFIGURING:
        get_component('configurator').request_done(_CONFIGURING.pop(DOMAIN))

    # Ensure component is loaded
    bootstrap.setup_component(hass, 'binary_sensor', config)

    calendars = load_config(hass.config.path(YAML_DEVICES))
    for calendar_hash, calendar in calendars.items():
        _CALENDARS.update({calendar_hash: calendar})
        platform_discovered(hass, calendar_hash)

    hass.services.call(DOMAIN, SERVICE_SCAN_CALENDARS, None)
    return True


def found_calendar(hass, calendar, track_new):
    """Check if we know about a calendar and generate PLATFORM_DISCOVER."""
    # since we could just use the global and not assign it
    import hashlib

    calendar_hash = hashlib.sha224(
        calendar['id'].encode('utf-8')).hexdigest()

    if _CALENDARS.get(calendar_hash, None) is not None:
        return

    # seriously, FU pylint
    _CALENDARS.update({calendar_hash: {
        CONF_CAL_ID: calendar['id'],
        CONF_NAME: calendar['summary'],
        CONF_ENTITIES: [{
            CONF_TRACK: track_new,
            CONF_SEARCH: None,
            CONF_NAME: calendar['summary']
        }]
    }})

    update_config(
        hass.config.path(YAML_DEVICES),
        calendar_hash,
        _CALENDARS[calendar_hash]
    )

    platform_discovered(hass, calendar_hash)


def platform_discovered(hass, calendar_hash):
    """Fire platform_discovered event."""
    # Fire thermostat discovery event
    hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
        ATTR_SERVICE: DISCOVER_BINARY_SENSORS,
        ATTR_DISCOVERED: _CALENDARS[calendar_hash]
    })


def get_next_event(hass, calendar_id, search=None):
    """Get the latest data."""
    from homeassistant.util import dt

    service = get_calendar_service(hass)
    params = dict(DEFAULT_GOOGLE_SEARCH_PARAMS)
    params['timeMin'] = dt.utcnow().isoformat('T')
    params['calendarId'] = calendar_id
    if search:
        params['q'] = search

    result = service.events().list(**params).execute()

    _LOGGER.error('Getting calendar data: [%s]', str(params))

    items = result.get('items', [])
    return items[0] if len(items) == 1 else None


def get_calendar_service(hass):
    """Get the calendar service from the storage file token."""
    # pylint disable=no-name-in-module,import-error
    import httplib2
    from oauth2client.file import Storage
    from googleapiclient import discovery
    token_file = hass.config.path(TOKEN_FILE)
    credentials = Storage(token_file).get()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)
    return service


def setup_scanner_platform(hass, config):
    """Setup the scanner to look for new calendars."""
    from homeassistant.util import convert
    from homeassistant.helpers.event import track_utc_time_change
    interval = convert(config.get(CONF_SCAN_INTERVAL), int,
                       DEFAULT_CONF_SCAN_INTERVAL)

    def calendar_tracker_scan(now):
        """Call up service and get list of calendars.

        Then call see_calendar() on each.

        """
        # pylint disable=unused-argument
        hass.services.call(DOMAIN, SERVICE_SCAN_CALENDARS, None)

    track_utc_time_change(hass,
                          calendar_tracker_scan,
                          minute=range(0, 60, interval),
                          second=0)


def load_config(path):
    """Load the google_calendar_devices.yaml."""
    import os
    from homeassistant.config import load_yaml_config_file
    calendars = {}
    if not os.path.isfile(path):
        return calendars

    return dict([(hash, DEVICE_SCHEMA(data)) for hash,
                 data in load_yaml_config_file(path).items()])


def update_config(path, calendar_hash, calendar):
    """Write the google_calendar_devices.yaml."""
    import yaml
    with open(path, 'a') as out:
        yaml.dump({calendar_hash: calendar}, out, default_flow_style=False)
