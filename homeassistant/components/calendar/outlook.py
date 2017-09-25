""" Outlook Calendar """
import logging
import os
import json
import time
import uuid
from datetime import timedelta
from urllib.parse import urlencode
import requests
import voluptuous as vol
from voluptuous.error import Error as VoluptuousError
import yaml

# Import the device class from the component that you want to support
import homeassistant.util.dt as dt_util
import homeassistant.loader as loader
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.core import callback
from homeassistant.components.calendar import CalendarEventDevice
from homeassistant.components.google import CONF_DEVICE_ID, CONF_NAME
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.helpers.entity import generate_entity_id

# Home Assistant depends on 3rd party packages for API specific code.
REQUIREMENTS = []

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
ATTR_ACCESS_TOKEN = 'access_token'
ATTR_REFRESH_TOKEN = 'refresh_token'

CONF_CAL_ID = 'cal_id'
CONF_ENTITIES = 'entities'
CONF_TRACK = 'track'
CONF_SEARCH = 'search'
CONF_OFFSET = 'offset'

DEFAULT_CONFIG = {}

OUTLOOK_AUTH_CALLBACK_PATH = '/api/outlook/callback'
OUTLOOK_AUTH_START = '/api/outlook'
OUTLOOK_CONFIG_FILE = 'outlook.conf'

NOTIFICATION_ID = 'outlook_calendar_notification'
NOTIFICATION_TITLE = 'Outlook Calendar Setup'

DATA_INDEX = 'outlook_calendars'
YAML_DEVICES = 'outlook_calendars.yaml'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CLIENT_ID): cv.string,
    vol.Required(CONF_CLIENT_SECRET): cv.string,
})

_SINGLE_CALSEARCH_CONFIG = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Optional(CONF_TRACK): cv.boolean,
    vol.Optional(CONF_SEARCH): vol.Any(cv.string, None),
    vol.Optional(CONF_OFFSET): cv.string,
})

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_CAL_ID): cv.string,
    vol.Required(CONF_ENTITIES, None):
        vol.All(cv.ensure_list, [_SINGLE_CALSEARCH_CONFIG]),
}, extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Outlook platform."""
    # Assign configuration variables.
    # The configuration check takes care they are present.
    client_id = config[CONF_CLIENT_ID]
    client_secret = config[CONF_CLIENT_SECRET]

    oauth = OutlookAuthHelper(hass, client_id, client_secret)
    if oauth.config_is_valid is False:
        request_app_setup(hass, config, oauth, add_devices)
        return False

    service = OutlookService(hass, oauth)
    add_devices(service.calendars)


def config_from_file(filename, config=None):
    """Small configuration file management function."""
    if config:
        # We"re writing configuration
        try:
            with open(filename, 'w') as fdesc:
                fdesc.write(json.dumps(config))
        except IOError as error:
            _LOGGER.error("Saving config file failed: %s", error)
            return False
        return config
    else:
        # We"re reading config
        if os.path.isfile(filename):
            try:
                with open(filename, 'r') as fdesc:
                    return json.loads(fdesc.read())
            except IOError as error:
                _LOGGER.error("Reading config file failed: %s", error)
                # This won"t work yet
                return False
        else:
            return {}


def request_app_setup(hass, config, oauth, add_devices):
    start_url = '{}{}'.format(hass.config.api.base_url,
                              OUTLOOK_AUTH_START)
    callback_url = '{}{}'.format(hass.config.api.base_url,
                                 OUTLOOK_AUTH_CALLBACK_PATH)

    outlook_auth_start_url = oauth.get_signin_url()

    print('Outlook.com Authenticate:{}'.format(outlook_auth_start_url))

    hass.http.register_redirect(OUTLOOK_AUTH_START,
                                outlook_auth_start_url)
    hass.http.register_view(
        OutlookAuthCallbackView(config, add_devices, oauth))

    persistent_notification = loader.get_component('persistent_notification')
    persistent_notification.create(
        hass, 'In order to authorize Home-Assistant<br/>'
              'to view your calendars<br />'
              'you must visit: <a href="{}" target="_blank">{}</a><br />'
              'Callback url: {}'
              ''.format(start_url, start_url, callback_url),
        title=NOTIFICATION_TITLE, notification_id=NOTIFICATION_ID
    )


class OutlookService():
    """ Service to interact with Outlook API v2.0 """
    outlook_api_endpoint = 'https://outlook.office.com/api/v2.0{0}'
    calendar_data = {}

    def __init__(self, hass, oauth):
        self.hass = hass
        self.oauth = oauth

    def make_api_call(self,
                      method,
                      url,
                      token,
                      payload=None,
                      parameters=None):
        """ Generic API Sending """
        # Send these headers with all API calls
        headers = {'User-Agent': 'HomeAssistant',
                   'Authorization': 'Bearer {0}'.format(token),
                   'Accept': 'application/json'}

        # Use these headers to instrument calls. Makes it easier
        # to correlate requests and responses in case of problems
        # and is a recommended best practice.
        request_id = str(uuid.uuid4())
        instrumentation = {'client-request-id': request_id,
                           'return-client-request-id': 'true'}

        headers.update(instrumentation)

        response = None

        if method.upper() == 'GET':
            response = requests.get(url,
                                    headers=headers,
                                    params=parameters)
        elif method.upper() == 'DELETE':
            response = requests.delete(url,
                                       headers=headers,
                                       params=parameters)
        elif method.upper() == 'PATCH':
            headers.update({'Content-Type': 'application/json'})
            data = json.dumps(payload)
            response = requests.patch(url,
                                      headers=headers,
                                      data=data,
                                      params=parameters)
        elif method.upper() == 'POST':
            headers.update({'Content-Type': 'application/json'})
            data = json.dumps(payload)
            response = requests.post(url,
                                     headers=headers,
                                     data=data,
                                     params=parameters)

        return response

    @property
    def calendars(self):
        if not self.load_config(self.hass.config.path(YAML_DEVICES)):
            self.scan_for_calendars()

        result = []
        for calendar in self.calendar_data.values():
            for entity in calendar[CONF_ENTITIES]:
                if entity[CONF_TRACK]:
                    result.append(
                        OutlookCalendarEventDevice(self.hass,
                                                   self,
                                                   calendar[CONF_CAL_ID],
                                                   entity))
        return result

    def scan_for_calendars(self):
        get_messages_url = self.outlook_api_endpoint.format('/Me/Calendars')
        access_token = self.oauth.get_access_token()

        # Use OData query parameters to control the results
        #  - Only first 10 results returned
        #  - Only return the ReceivedDateTime, Subject, and From fields
        #  - Sort the results by the ReceivedDateTime field in desc order
        # query_parameters = {'$top': '10',
        #                     '$select': 'ReceivedDateTime,Subject,From',
        #                     '$orderby': 'ReceivedDateTime DESC'}

        result = self.make_api_call('GET', get_messages_url, access_token)

        if result.status_code == requests.codes.get('ok'):
            json_data = result.json()
            for json_calendar in json_data["value"]:
                cal = self.get_calendar_info(json_calendar)
                if self.calendar_data.get(cal[CONF_CAL_ID], None) is not None:
                    continue

                self.calendar_data.update({cal[CONF_CAL_ID]: cal})
                self.update_config(
                    self.hass.config.path(YAML_DEVICES),
                    self.calendar_data[cal[CONF_CAL_ID]]
                )

    def get_calendar_first_event(self, calendar_id):
        path = '/Me/Calendars/{0}/calendarview'.format(calendar_id)
        get_calendarview_url = self.outlook_api_endpoint.format(path)
        access_token = self.oauth.get_access_token()

        start = dt_util.now()
        end = start + dt_util.dt.timedelta(days=1)
        query_parameters = {'startDateTime': start.isoformat('T'),
                            'endDateTime': end.isoformat('T'),
                            '$top': '1',
                            '$select': 'Subject,Start,End,IsAllDay'}

        print(query_parameters)

        result = self.make_api_call('GET',
                                    get_calendarview_url,
                                    access_token,
                                    parameters=query_parameters)

        if result.status_code == requests.codes.get('ok'):
            json_data = result.json()
            events = json_data['value']
            if len(events) == 1:
                event = events[0]
                # date = 'date' if event['IsAllDay'] else 'dateTime'
                # print(date)
                return {'start': {'dateTime': event['Start']['DateTime']},
                        'end': {'dateTime': event['End']['DateTime']},
                        'summary': event['Subject']}
        return None

    def get_calendar_info(self, json_calendar):
        """Convert data from Outlook into DEVICE_SCHEMA."""
        calendar_info = DEVICE_SCHEMA({
            CONF_CAL_ID: json_calendar['Id'],
            CONF_ENTITIES: [{
                CONF_TRACK: True,
                CONF_NAME: json_calendar['Name'],
                CONF_DEVICE_ID: generate_entity_id('{}',
                                                   json_calendar['Name'],
                                                   hass=self.hass),
            }]
        })
        return calendar_info

    def load_config(self, path):
        """Load the outlook_calendar.yaml."""
        self.calendar_data = {}
        try:
            with open(path) as file:
                data = yaml.load(file)
                for calendar in data:
                    try:
                        self.calendar_data.update(
                            {calendar[CONF_CAL_ID]: DEVICE_SCHEMA(calendar)})
                    except VoluptuousError as exc:
                        # keep going
                        _LOGGER.warning('Calendar Invalid Data: %s', exc)
        except FileNotFoundError:
            # When YAML file could not be loaded/did not contain a dict
            return False

        return True

    def update_config(self, path, calendar):
        """Write the outlook_calendar.yaml."""
        with open(path, 'a') as out:
            out.write('\n')
            yaml.dump([calendar], out, default_flow_style=False)


class OutlookAuthCallbackView(HomeAssistantView):
    """Handle OAuth finish callback requests."""

    requires_auth = False
    url = '/api/outlook/callback'
    name = 'api:outlook:callback'

    def __init__(self, config, add_devices, oauth):
        """Initialize the OAuth callback view."""
        self.config = config
        self.add_devices = add_devices
        self.oauth = oauth

    @callback
    def get(self, request):
        """Finish OAuth callback request."""

        hass = request.app['hass']
        data = request.GET

        response_message = """Outlook has been successfully authorized!
            You can close this window now!"""

        if data.get('code') is not None:
            self.oauth.get_token_from_code(data.get('code'))
        else:
            _LOGGER.error("Unknown error when authing")
            response_message = """Something went wrong when
                attempting authenticating with Outlook.
                An unknown error occurred. Please try again!
                """

        html_response = """<html><head><title>Outlook Auth</title></head>
        <body><h1>{}</h1></body></html>""".format(response_message)

        # config_contents = {
        #     ATTR_ACCESS_TOKEN: self.oauth.token['access_token'],
        #     ATTR_REFRESH_TOKEN: self.oauth.token['refresh_token']
        # }
        if not config_from_file(hass.config.path(OUTLOOK_CONFIG_FILE),
                                self.oauth.token):
            _LOGGER.error("Failed to save config file")

        hass.async_add_job(setup_platform,
                           hass,
                           self.config,
                           self.add_devices)

        return html_response


class OutlookCalendarEventDevice(CalendarEventDevice):
    """An Outlook calendar event device."""

    def __init__(self, hass, calendar_service, calendar, data):
        """The same as a google calendar but without the api calls."""
        self.data = OutlookCalendarData(calendar_service,
                                        calendar,
                                        data.get('search', None))
        super().__init__(hass, data)


class OutlookCalendarData(object):
    """Class to utilize calendar service object to get next event."""

    def __init__(self, calendar_service, calendar_id, search=None):
        """Setup how we are going to search the google calendar."""
        self.calendar_service = calendar_service
        self.calendar_id = calendar_id
        self.search = search
        self.event = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        self.event = self.calendar_service.get_calendar_first_event(
            self.calendar_id)
        return True


class OutlookAuthHelper:
    """Class to perform Auth on the Outlook platform."""
    # Constant strings for OAuth2 flow
    # The OAuth authority
    authority = 'https://login.microsoftonline.com'

    # The authorize URL that initiates the OAuth2 client credential flow
    # for admin consent
    authorize_url = '{0}{1}'.format(authority,
                                    '/common/oauth2/v2.0/authorize?{0}')

    # The token issuing endpoint
    token_url = '{0}{1}'.format(authority,
                                '/common/oauth2/v2.0/token')

    # The scopes required by the app
    scopes = ['openid',
              'offline_access',
              'https://outlook.office.com/calendars.read']

    def __init__(self, hass, client_id, client_secret):
        self.token = {}
        self.hass = hass
        self.client_id = client_id
        self.client_secret = client_secret

    def get_signin_url(self):
        # Build the query parameters for the signin url
        params = {'client_id': self.client_id,
                  'redirect_uri': self.redirect_uri,
                  'response_type': 'code',
                  'scope': ' '.join(str(i) for i in self.scopes)}

        signin_url = self.authorize_url.format(urlencode(params))
        return signin_url

    def get_token_from_code(self, auth_code):
        # Build the post form for the token request
        post_data = {'grant_type': 'authorization_code',
                     'code': auth_code,
                     'redirect_uri': self.redirect_uri,
                     'scope': ' '.join(str(i) for i in self.scopes),
                     'client_id': self.client_id,
                     'client_secret': self.client_secret}

        res = requests.post(self.token_url, data=post_data)
        try:
            self.token = res.json()
            self.calc_expiration()
            return self.token
        except ValueError:
            return 'Error retrieving token: {0} - {1}'.format(res.status_code,
                                                              res.text)

    def get_token_from_refresh_token(self):
        # Build the post form for the token request
        post_data = {'grant_type': 'refresh_token',
                     'refresh_token': self.token.get('refresh_token'),
                     'redirect_uri': self.redirect_uri,
                     'scope': ' '.join(str(i) for i in self.scopes),
                     'client_id': self.client_id,
                     'client_secret': self.client_secret}
        res = requests.post(self.token_url, data=post_data)
        try:
            self.token = res.json()
            self.calc_expiration()
            return self.token
        except ValueError:
            return 'Error retrieving token: {0} - {1}'.format(res.status_code,
                                                              res.text)

    def calc_expiration(self):
        expiration = int(time.time()) + self.token['expires_in'] - 300
        self.token['token_expires'] = expiration

    def get_access_token(self):
        current_token = self.token.get(ATTR_ACCESS_TOKEN)
        expiration = self.token.get('token_expires')
        now = int(time.time())
        if current_token and expiration and now < expiration:
            # Token still valid
            return current_token
        else:
            # Token expired
            self.get_token_from_refresh_token()
            return self.token.get(ATTR_ACCESS_TOKEN)

    @property
    def redirect_uri(self):
        return '{}{}'.format(self.hass.config.api.base_url,
                             OUTLOOK_AUTH_CALLBACK_PATH)

    @property
    def config_is_valid(self):
        config_path = self.hass.config.path(OUTLOOK_CONFIG_FILE)
        if os.path.isfile(config_path):
            self.token = config_from_file(config_path)
            if self.token == DEFAULT_CONFIG:
                return False
        else:
            self.token = config_from_file(config_path, DEFAULT_CONFIG)
            return False

        return True
