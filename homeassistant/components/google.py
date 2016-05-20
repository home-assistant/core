"""
Support for Google - Calendar Event Devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/google/

NOTE: IF YOU ADD MORE TO THIS THAN JUST CALENDAR THEN USERS WILL NEED TO
DELETE THEIR TOKEN_FILE. THEY WILL LOSE THEIR REFRESH_TOKEN PIECE WHEN
RE-AUTHENTICATING TO ADD MORE API ACCESS
"""
import os
import logging
import socket
from datetime import timedelta
import yaml
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant import bootstrap
from homeassistant.const import HTTP_OK
from homeassistant.util import get_local_ip, convert, dt
from homeassistant.loader import get_component
from homeassistant.config import load_yaml_config_file
from homeassistant.components.discovery import discover

REQUIREMENTS = [
    'google-api-python-client==1.5.0',
]
DEPENDENCIES = ['http', 'calendar']

_LOGGER = logging.getLogger(__name__)
_CONFIGURING = {}

DOMAIN = 'google'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_FQDN = 'fqdn'
CONF_TRACK_NEW = 'track_new_calendar'
CONF_CAL_ID = 'cal_id'
CONF_NAME = 'name'
CONF_ENTITIES = 'entities'
CONF_TRACK = 'track'
CONF_SEARCH = 'search'
CONF_OFFSET = 'offset'

DEFAULT_CONF_TRACK_NEW = True
DEFAULT_CONF_OFFSET = '#-'

DEFAULT_GOOGLE_SEARCH_PARAMS = {
    'orderBy': 'startTime',
    'maxResults': 1,
    'singleEvents': True,
}

GROUP_NAME_ALL_CALENDARS = "Google Calendar Sensors"

DISCOVER_CALENDARS = '{}.calendar'.format(DOMAIN)
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
})

_SINGLE_CALSEARCH_CONFIG = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_TRACK): cv.boolean,
    vol.Optional(CONF_SEARCH): vol.Any(cv.string, None),
    vol.Optional(CONF_OFFSET): cv.string,
})

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_CAL_ID): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_ENTITIES, None):
        vol.All(cv.ensure_list, [_SINGLE_CALSEARCH_CONFIG]),
}, extra=vol.ALLOW_EXTRA)

_CALENDARS = {}
_OAUTH_PATH_SETUP = False


def validate_ip(host):
    """Validate if a string is an ip."""
    parts = host.split('.')
    return all([len(parts) == 4] +
               [p.isdigit() and int(p) < 256 and int(p) >= 0 for p in parts])


def get_hostname(hass):
    """Try to return a valid fully qualifed domain name."""
    num_dots = len(hass.http.server_address[0].split('.'))
    if not validate_ip(hass.http.server_address[0]) and num_dots > 1:
        # we think we have a valid fqdn
        return hass.http.server_address[0]

    # last ditch effor, try to get it from socket
    try:
        hostname = socket.gethostbyaddr(get_local_ip())[0]
        return hostname
    except socket.gaierror:
        _LOGGER.error('Please set your server_host')

    raise Exception('Unable to get the hostname automatically, ' +
                    'you need to set http:server_host: to a ' +
                    'fully qualified domain name eg. ha.example.com' +
                    'Please see setup instructions for component')


def setup_oauth_paths(hass, config):
    """Start setup of app with Google Oauth."""
    # pylint disable=global-statement
    from oauth2client import client
    base_url = "{}://{}:{}".format(
        'https' if hass.http.use_ssl else 'http',
        get_hostname(hass),
        hass.http.server_address[1])
    _LOGGER.error(base_url)

    global _OAUTH_PATH_SETUP
    if _OAUTH_PATH_SETUP:
        return

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
        # pylint: disable=unused-argument
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
                You can now close this window.
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
    configurator = get_component('configurator')
    if DOMAIN in _CONFIGURING:
        configurator.notify_errors(_CONFIGURING[DOMAIN],
                                   "Failed to register, please try again.")
        return False

    setup_oauth_paths(hass, config)

    description = """Authenticate your Google account: """

    def _configuration_callback(callback_data):
        """What actions to do when user clicks button."""
        # pylint: disable=unused-argument
        token_file = hass.config.path(TOKEN_FILE)
        if not os.path.isfile(token_file):
            configurator.notify_errors(_CONFIGURING[DOMAIN],
                                       """Failed to token file,
                                       please try again.""")
            return False
        configurator.request_done(_CONFIGURING.pop(DOMAIN))
        do_setup(hass, config)
        return True

    _CONFIGURING[DOMAIN] = configurator.request_config(
        hass,
        'Google Calendar Authentication',
        _configuration_callback,
        description=description,
        submit_caption="I have created the JSON file",
        link_name='Login to Google',
        link_url=CAL_SEARCH_START,
    )


def request_api_setup(hass, config):
    """Request completion of oauth setup."""
    configurator = get_component('configurator')
    if DOMAIN in _CONFIGURING:
        return False

    description = """Please setup Google API per: """

    def _configuration_callback(callback_data):
        """What actions to do when user clicks button."""
        # pylint: disable=unused-argument
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
        'Google Calendar OAuth Setup',
        _configuration_callback,
        description=description,
        submit_caption="I have created the JSON file",
        link_name='Google Calendar Component Setup',
        link_url='https://home-assistant.io/components/google/',
    )


def do_setup_check(hass, config):
    """Verify that we have both the Google Api setup and Oauth."""
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
    config = config.get(DOMAIN, {})
    if isinstance(config, list) and len(config) > 0:
        config = config[0]

    # this will raise an exception if it can't get a hostname
    # this is a fatal exception since authentication can't happen
    # unless we have a fully qualified domain name
    get_hostname(hass)

    if not do_setup_check(hass, config):
        return False

    do_setup(hass, config)
    return True


def do_setup(hass, config):
    """Run the setup after we have everything configured."""
    # pylint: disable=global-statement
    if DOMAIN in _CONFIGURING:
        get_component('configurator').request_done(_CONFIGURING.pop(DOMAIN))

    def _scan_for_calendars(service):
        """Scan for new calendars."""
        track_new = convert(config.get(CONF_TRACK_NEW),
                            bool, DEFAULT_CONF_TRACK_NEW)
        service = get_calendar_service(hass)
        cal_list = service.calendarList()  # pylint: disable=no-member
        calendars = cal_list.list().execute()['items']
        for calendar in calendars:
            found_calendar(hass, calendar, track_new)

    hass.services.register(
        DOMAIN, SERVICE_SCAN_CALENDARS, _scan_for_calendars,
        None, schema=None)

    # Ensure component is loaded
    bootstrap.setup_component(hass, 'calendar', config)

    calendars = load_config(hass.config.path(YAML_DEVICES))
    for calendar_hash, calendar in calendars.items():
        _CALENDARS.update({calendar_hash: calendar})
        discover(hass, DISCOVER_CALENDARS, _CALENDARS[calendar_hash])

    hass.services.call(DOMAIN, SERVICE_SCAN_CALENDARS, None)
    return True


def found_calendar(hass, calendar, track_new):
    """Check if we know about a calendar and generate PLATFORM_DISCOVER."""
    import hashlib
    calendar_hash = hashlib.sha224(
        calendar['id'].encode('utf-8')).hexdigest()

    if _CALENDARS.get(calendar_hash, None) is not None:
        return

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

    discover(hass, DISCOVER_CALENDARS, _CALENDARS[calendar_hash])


def get_next_event(hass, calendar_id, search=None):
    """Get the latest data."""
    service = get_calendar_service(hass)
    params = dict(DEFAULT_GOOGLE_SEARCH_PARAMS)
    params['timeMin'] = dt.utcnow().isoformat('T')
    params['calendarId'] = calendar_id
    if search:
        params['q'] = search

    events = service.events()  # pylint: disable=no-member
    result = events.list(**params).execute()

    items = result.get('items', [])
    return items[0] if len(items) == 1 else None


def get_calendar_service(hass):
    """Get the calendar service from the storage file token."""
    import httplib2
    from oauth2client.file import Storage
    from googleapiclient import discovery
    token_file = hass.config.path(TOKEN_FILE)
    credentials = Storage(token_file).get()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)
    return service


def load_config(path):
    """Load the google_calendar_devices.yaml."""
    calendars = {}
    if not os.path.isfile(path):
        return calendars

    return dict([(hash, DEVICE_SCHEMA(data)) for hash,
                 data in load_yaml_config_file(path).items()])


def update_config(path, calendar_hash, calendar):
    """Write the google_calendar_devices.yaml."""
    with open(path, 'a') as out:
        yaml.dump({calendar_hash: calendar}, out, default_flow_style=False)
