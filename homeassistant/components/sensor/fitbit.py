"""
Support for the Fitbit API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fitbit/
"""
import os
import json
import logging
import datetime
import time

from homeassistant.const import HTTP_OK, TEMP_CELSIUS
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity
from homeassistant.loader import get_component

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ["fitbit==0.2.2"]
DEPENDENCIES = ["http"]

ICON = "mdi:walk"

_CONFIGURING = {}

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=30)

FITBIT_AUTH_START = "/auth/fitbit"
FITBIT_AUTH_CALLBACK_PATH = "/auth/fitbit/callback"

DEFAULT_CONFIG = {
    "client_id": "CLIENT_ID_HERE",
    "client_secret": "CLIENT_SECRET_HERE"
}

FITBIT_CONFIG_FILE = "fitbit.conf"

FITBIT_RESOURCES_LIST = {
    "activities/activityCalories": "cal",
    "activities/calories": "cal",
    "activities/caloriesBMR": "cal",
    "activities/distance": "",
    "activities/elevation": "",
    "activities/floors": "floors",
    "activities/heart": "bpm",
    "activities/minutesFairlyActive": "minutes",
    "activities/minutesLightlyActive": "minutes",
    "activities/minutesSedentary": "minutes",
    "activities/minutesVeryActive": "minutes",
    "activities/steps": "steps",
    "activities/tracker/activityCalories": "cal",
    "activities/tracker/calories": "cal",
    "activities/tracker/distance": "",
    "activities/tracker/elevation": "",
    "activities/tracker/floors": "floors",
    "activities/tracker/minutesFairlyActive": "minutes",
    "activities/tracker/minutesLightlyActive": "minutes",
    "activities/tracker/minutesSedentary": "minutes",
    "activities/tracker/minutesVeryActive": "minutes",
    "activities/tracker/steps": "steps",
    "body/bmi": "BMI",
    "body/fat": "%",
    "sleep/awakeningsCount": "times awaken",
    "sleep/efficiency": "%",
    "sleep/minutesAfterWakeup": "minutes",
    "sleep/minutesAsleep": "minutes",
    "sleep/minutesAwake": "minutes",
    "sleep/minutesToFallAsleep": "minutes",
    "sleep/startTime": "start time",
    "sleep/timeInBed": "time in bed",
    "body/weight": ""
}

FITBIT_DEFAULT_RESOURCE_LIST = ["activities/steps"]

FITBIT_MEASUREMENTS = {
    "en_US": {
        "duration": "ms",
        "distance": "mi",
        "elevation": "ft",
        "height": "in",
        "weight": "lbs",
        "body": "in",
        "liquids": "fl. oz.",
        "blood glucose": "mg/dL",
    },
    "en_GB": {
        "duration": "milliseconds",
        "distance": "kilometers",
        "elevation": "meters",
        "height": "centimeters",
        "weight": "stone",
        "body": "centimeters",
        "liquids": "milliliters",
        "blood glucose": "mmol/L"
    },
    "metric": {
        "duration": "milliseconds",
        "distance": "kilometers",
        "elevation": "meters",
        "height": "centimeters",
        "weight": "kilograms",
        "body": "centimeters",
        "liquids": "milliliters",
        "blood glucose": "mmol/L"
    }
}


def config_from_file(filename, config=None):
    """Small configuration file management function."""
    if config:
        # We"re writing configuration
        try:
            with open(filename, "w") as fdesc:
                fdesc.write(json.dumps(config))
        except IOError as error:
            _LOGGER.error("Saving config file failed: %s", error)
            return False
        return config
    else:
        # We"re reading config
        if os.path.isfile(filename):
            try:
                with open(filename, "r") as fdesc:
                    return json.loads(fdesc.read())
            except IOError as error:
                _LOGGER.error("Reading config file failed: %s", error)
                # This won"t work yet
                return False
        else:
            return {}


def request_app_setup(hass, config, add_devices, config_path,
                      discovery_info=None):
    """Assist user with configuring the Fitbit dev application."""
    configurator = get_component("configurator")

    # pylint: disable=unused-argument
    def fitbit_configuration_callback(callback_data):
        """The actions to do when our configuration callback is called."""
        config_path = hass.config.path(FITBIT_CONFIG_FILE)
        if os.path.isfile(config_path):
            config_file = config_from_file(config_path)
            if config_file == DEFAULT_CONFIG:
                error_msg = ("You didn't correctly modify fitbit.conf",
                             " please try again")
                configurator.notify_errors(_CONFIGURING["fitbit"], error_msg)
            else:
                setup_platform(hass, config, add_devices, discovery_info)
        else:
            setup_platform(hass, config, add_devices, discovery_info)

    start_url = "{}{}".format(hass.config.api.base_url,
                              FITBIT_AUTH_CALLBACK_PATH)

    description = """Please create a Fitbit developer app at
                       https://dev.fitbit.com/apps/new.
                       For the OAuth 2.0 Application Type choose Personal.
                       Set the Callback URL to {}.
                       They will provide you a Client ID and secret.
                       These need to be saved into the file located at: {}.
                       Then come back here and hit the below button.
                       """.format(start_url, config_path)

    submit = "I have saved my Client ID and Client Secret into fitbit.conf."

    _CONFIGURING["fitbit"] = configurator.request_config(
        hass, "Fitbit", fitbit_configuration_callback,
        description=description, submit_caption=submit,
        description_image="/static/images/config_fitbit_app.png"
    )


def request_oauth_completion(hass):
    """Request user complete Fitbit OAuth2 flow."""
    configurator = get_component("configurator")
    if "fitbit" in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING["fitbit"], "Failed to register, please try again.")

        return

    # pylint: disable=unused-argument
    def fitbit_configuration_callback(callback_data):
        """The actions to do when our configuration callback is called."""

    start_url = "{}{}".format(hass.config.api.base_url, FITBIT_AUTH_START)

    description = "Please authorize Fitbit by visiting {}".format(start_url)

    _CONFIGURING["fitbit"] = configurator.request_config(
        hass, "Fitbit", fitbit_configuration_callback,
        description=description,
        submit_caption="I have authorized Fitbit."
    )

# pylint: disable=too-many-locals


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Fitbit sensor."""
    config_path = hass.config.path(FITBIT_CONFIG_FILE)
    if os.path.isfile(config_path):
        config_file = config_from_file(config_path)
        if config_file == DEFAULT_CONFIG:
            request_app_setup(hass, config, add_devices, config_path,
                              discovery_info=None)
            return False
    else:
        config_file = config_from_file(config_path, DEFAULT_CONFIG)
        request_app_setup(hass, config, add_devices, config_path,
                          discovery_info=None)
        return False

    if "fitbit" in _CONFIGURING:
        get_component("configurator").request_done(_CONFIGURING.pop("fitbit"))

    import fitbit

    access_token = config_file.get("access_token")
    refresh_token = config_file.get("refresh_token")
    if None not in (access_token, refresh_token):
        authd_client = fitbit.Fitbit(config_file.get("client_id"),
                                     config_file.get("client_secret"),
                                     access_token=access_token,
                                     refresh_token=refresh_token)

        if int(time.time()) - config_file.get("last_saved_at", 0) > 3600:
            authd_client.client.refresh_token()

        authd_client.system = authd_client.user_profile_get()["user"]["locale"]

        dev = []
        for resource in config.get("monitored_resources",
                                   FITBIT_DEFAULT_RESOURCE_LIST):
            dev.append(FitbitSensor(authd_client, config_path, resource,
                                    hass.config.temperature_unit ==
                                    TEMP_CELSIUS))
        add_devices(dev)

    else:
        oauth = fitbit.api.FitbitOauth2Client(config_file.get("client_id"),
                                              config_file.get("client_secret"))

        redirect_uri = "{}{}".format(hass.config.api.base_url,
                                     FITBIT_AUTH_CALLBACK_PATH)

        def _start_fitbit_auth(handler, path_match, data):
            """Start Fitbit OAuth2 flow."""
            url, _ = oauth.authorize_token_url(redirect_uri=redirect_uri,
                                               scope=["activity", "heartrate",
                                                      "nutrition", "profile",
                                                      "settings", "sleep",
                                                      "weight"])
            handler.send_response(301)
            handler.send_header("Location", url)
            handler.end_headers()

        def _finish_fitbit_auth(handler, path_match, data):
            """Finish Fitbit OAuth2 flow."""
            response_message = """Fitbit has been successfully authorized!
            You can close this window now!"""
            from oauthlib.oauth2.rfc6749.errors import MismatchingStateError
            from oauthlib.oauth2.rfc6749.errors import MissingTokenError
            if data.get("code") is not None:
                try:
                    oauth.fetch_access_token(data.get("code"), redirect_uri)
                except MissingTokenError as error:
                    _LOGGER.error("Missing token: %s", error)
                    response_message = """Something went wrong when
                    attempting authenticating with Fitbit. The error
                    encountered was {}. Please try again!""".format(error)
                except MismatchingStateError as error:
                    _LOGGER.error("Mismatched state, CSRF error: %s", error)
                    response_message = """Something went wrong when
                    attempting authenticating with Fitbit. The error
                    encountered was {}. Please try again!""".format(error)
            else:
                _LOGGER.error("Unknown error when authing")
                response_message = """Something went wrong when
                    attempting authenticating with Fitbit.
                    An unknown error occurred. Please try again!
                    """

            html_response = """<html><head><title>Fitbit Auth</title></head>
            <body><h1>{}</h1></body></html>""".format(response_message)

            html_response = html_response.encode("utf-8")

            handler.send_response(HTTP_OK)
            handler.write_content(html_response, content_type="text/html")

            config_contents = {
                "access_token": oauth.token["access_token"],
                "refresh_token": oauth.token["refresh_token"],
                "client_id": oauth.client_id,
                "client_secret": oauth.client_secret
            }
            if not config_from_file(config_path, config_contents):
                _LOGGER.error("failed to save config file")

            setup_platform(hass, config, add_devices, discovery_info=None)

        hass.http.register_path("GET", FITBIT_AUTH_START, _start_fitbit_auth,
                                require_auth=False)
        hass.http.register_path("GET", FITBIT_AUTH_CALLBACK_PATH,
                                _finish_fitbit_auth, require_auth=False)

        request_oauth_completion(hass)


# pylint: disable=too-few-public-methods
class FitbitSensor(Entity):
    """Implementation of a Fitbit sensor."""

    def __init__(self, client, config_path, resource_type, is_metric):
        """Initialize the Fitbit sensor."""
        self.client = client
        self.config_path = config_path
        self.resource_type = resource_type
        pretty_resource = self.resource_type.replace("activities/", "")
        pretty_resource = pretty_resource.replace("/", " ")
        pretty_resource = pretty_resource.title()
        if pretty_resource == "Body Bmi":
            pretty_resource = "BMI"
        self._name = pretty_resource
        unit_type = FITBIT_RESOURCES_LIST[self.resource_type]
        if unit_type == "":
            split_resource = self.resource_type.split("/")
            try:
                measurement_system = FITBIT_MEASUREMENTS[self.client.system]
            except KeyError:
                if is_metric:
                    measurement_system = FITBIT_MEASUREMENTS["metric"]
                else:
                    measurement_system = FITBIT_MEASUREMENTS["en_US"]
            unit_type = measurement_system[split_resource[-1]]
        self._unit_of_measurement = unit_type
        self._state = 0
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    # pylint: disable=too-many-branches
    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the Fitbit API and update the states."""
        container = self.resource_type.replace("/", "-")
        response = self.client.time_series(self.resource_type, period="7d")
        self._state = response[container][-1].get("value")
        if self.resource_type == "activities/heart":
            self._state = response[container][-1].get("restingHeartRate")
        config_contents = {
            "access_token": self.client.client.token["access_token"],
            "refresh_token": self.client.client.token["refresh_token"],
            "client_id": self.client.client.client_id,
            "client_secret": self.client.client.client_secret,
            "last_saved_at": int(time.time())
        }
        if not config_from_file(self.config_path, config_contents):
            _LOGGER.error("failed to save config file")
