"""Support for the Fitbit API."""
import datetime
import logging
import os
import time

from fitbit import Fitbit
from fitbit.api import FitbitOauth2Client
from oauthlib.oauth2.rfc6749.errors import MismatchingStateError, MissingTokenError
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_UNIT_SYSTEM,
    MASS_KILOGRAMS,
    MASS_MILLIGRAMS,
    TIME_MILLISECONDS,
    TIME_MINUTES,
    UNIT_PERCENTAGE,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.network import get_url
from homeassistant.util.json import load_json, save_json

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

ATTR_ACCESS_TOKEN = "access_token"
ATTR_REFRESH_TOKEN = "refresh_token"
ATTR_CLIENT_ID = "client_id"
ATTR_CLIENT_SECRET = "client_secret"
ATTR_LAST_SAVED_AT = "last_saved_at"

CONF_MONITORED_RESOURCES = "monitored_resources"
CONF_CLOCK_FORMAT = "clock_format"
ATTRIBUTION = "Data provided by Fitbit.com"

FITBIT_AUTH_CALLBACK_PATH = "/api/fitbit/callback"
FITBIT_AUTH_START = "/api/fitbit"
FITBIT_CONFIG_FILE = "fitbit.conf"
FITBIT_DEFAULT_RESOURCES = ["activities/steps"]

SCAN_INTERVAL = datetime.timedelta(minutes=30)

DEFAULT_CONFIG = {"client_id": "CLIENT_ID_HERE", "client_secret": "CLIENT_SECRET_HERE"}

FITBIT_RESOURCES_LIST = {
    "activities/activityCalories": ["Activity Calories", "cal", "fire"],
    "activities/calories": ["Calories", "cal", "fire"],
    "activities/caloriesBMR": ["Calories BMR", "cal", "fire"],
    "activities/distance": ["Distance", "", "map-marker"],
    "activities/elevation": ["Elevation", "", "walk"],
    "activities/floors": ["Floors", "floors", "walk"],
    "activities/heart": ["Resting Heart Rate", "bpm", "heart-pulse"],
    "activities/minutesFairlyActive": ["Minutes Fairly Active", TIME_MINUTES, "walk"],
    "activities/minutesLightlyActive": ["Minutes Lightly Active", TIME_MINUTES, "walk"],
    "activities/minutesSedentary": [
        "Minutes Sedentary",
        TIME_MINUTES,
        "seat-recline-normal",
    ],
    "activities/minutesVeryActive": ["Minutes Very Active", TIME_MINUTES, "run"],
    "activities/steps": ["Steps", "steps", "walk"],
    "activities/tracker/activityCalories": ["Tracker Activity Calories", "cal", "fire"],
    "activities/tracker/calories": ["Tracker Calories", "cal", "fire"],
    "activities/tracker/distance": ["Tracker Distance", "", "map-marker"],
    "activities/tracker/elevation": ["Tracker Elevation", "", "walk"],
    "activities/tracker/floors": ["Tracker Floors", "floors", "walk"],
    "activities/tracker/minutesFairlyActive": [
        "Tracker Minutes Fairly Active",
        TIME_MINUTES,
        "walk",
    ],
    "activities/tracker/minutesLightlyActive": [
        "Tracker Minutes Lightly Active",
        TIME_MINUTES,
        "walk",
    ],
    "activities/tracker/minutesSedentary": [
        "Tracker Minutes Sedentary",
        TIME_MINUTES,
        "seat-recline-normal",
    ],
    "activities/tracker/minutesVeryActive": [
        "Tracker Minutes Very Active",
        TIME_MINUTES,
        "run",
    ],
    "activities/tracker/steps": ["Tracker Steps", "steps", "walk"],
    "body/bmi": ["BMI", "BMI", "human"],
    "body/fat": ["Body Fat", UNIT_PERCENTAGE, "human"],
    "body/weight": ["Weight", "", "human"],
    "devices/battery": ["Battery", None, None],
    "sleep/awakeningsCount": ["Awakenings Count", "times awaken", "sleep"],
    "sleep/efficiency": ["Sleep Efficiency", UNIT_PERCENTAGE, "sleep"],
    "sleep/minutesAfterWakeup": ["Minutes After Wakeup", TIME_MINUTES, "sleep"],
    "sleep/minutesAsleep": ["Sleep Minutes Asleep", TIME_MINUTES, "sleep"],
    "sleep/minutesAwake": ["Sleep Minutes Awake", TIME_MINUTES, "sleep"],
    "sleep/minutesToFallAsleep": [
        "Sleep Minutes to Fall Asleep",
        TIME_MINUTES,
        "sleep",
    ],
    "sleep/startTime": ["Sleep Start Time", None, "clock"],
    "sleep/timeInBed": ["Sleep Time in Bed", TIME_MINUTES, "hotel"],
}

FITBIT_MEASUREMENTS = {
    "en_US": {
        "duration": TIME_MILLISECONDS,
        "distance": "mi",
        "elevation": "ft",
        "height": "in",
        "weight": "lbs",
        "body": "in",
        "liquids": "fl. oz.",
        "blood glucose": f"{MASS_MILLIGRAMS}/dL",
        "battery": "",
    },
    "en_GB": {
        "duration": TIME_MILLISECONDS,
        "distance": "kilometers",
        "elevation": "meters",
        "height": "centimeters",
        "weight": "stone",
        "body": "centimeters",
        "liquids": "milliliters",
        "blood glucose": "mmol/L",
        "battery": "",
    },
    "metric": {
        "duration": TIME_MILLISECONDS,
        "distance": "kilometers",
        "elevation": "meters",
        "height": "centimeters",
        "weight": MASS_KILOGRAMS,
        "body": "centimeters",
        "liquids": "milliliters",
        "blood glucose": "mmol/L",
        "battery": "",
    },
}

BATTERY_LEVELS = {"High": 100, "Medium": 50, "Low": 20, "Empty": 0}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_MONITORED_RESOURCES, default=FITBIT_DEFAULT_RESOURCES
        ): vol.All(cv.ensure_list, [vol.In(FITBIT_RESOURCES_LIST)]),
        vol.Optional(CONF_CLOCK_FORMAT, default="24H"): vol.In(["12H", "24H"]),
        vol.Optional(CONF_UNIT_SYSTEM, default="default"): vol.In(
            ["en_GB", "en_US", "metric", "default"]
        ),
    }
)


def request_app_setup(hass, config, add_entities, config_path, discovery_info=None):
    """Assist user with configuring the Fitbit dev application."""
    configurator = hass.components.configurator

    def fitbit_configuration_callback(callback_data):
        """Handle configuration updates."""
        config_path = hass.config.path(FITBIT_CONFIG_FILE)
        if os.path.isfile(config_path):
            config_file = load_json(config_path)
            if config_file == DEFAULT_CONFIG:
                error_msg = (
                    "You didn't correctly modify fitbit.conf",
                    " please try again",
                )
                configurator.notify_errors(_CONFIGURING["fitbit"], error_msg)
            else:
                setup_platform(hass, config, add_entities, discovery_info)
        else:
            setup_platform(hass, config, add_entities, discovery_info)

    start_url = f"{get_url(hass)}{FITBIT_AUTH_CALLBACK_PATH}"

    description = f"""Please create a Fitbit developer app at
                       https://dev.fitbit.com/apps/new.
                       For the OAuth 2.0 Application Type choose Personal.
                       Set the Callback URL to {start_url}.
                       They will provide you a Client ID and secret.
                       These need to be saved into the file located at: {config_path}.
                       Then come back here and hit the below button.
                       """

    submit = "I have saved my Client ID and Client Secret into fitbit.conf."

    _CONFIGURING["fitbit"] = configurator.request_config(
        "Fitbit",
        fitbit_configuration_callback,
        description=description,
        submit_caption=submit,
        description_image="/static/images/config_fitbit_app.png",
    )


def request_oauth_completion(hass):
    """Request user complete Fitbit OAuth2 flow."""
    configurator = hass.components.configurator
    if "fitbit" in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING["fitbit"], "Failed to register, please try again."
        )

        return

    def fitbit_configuration_callback(callback_data):
        """Handle configuration updates."""

    start_url = f"{get_url(hass)}{FITBIT_AUTH_START}"

    description = f"Please authorize Fitbit by visiting {start_url}"

    _CONFIGURING["fitbit"] = configurator.request_config(
        "Fitbit",
        fitbit_configuration_callback,
        description=description,
        submit_caption="I have authorized Fitbit.",
    )


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Fitbit sensor."""
    config_path = hass.config.path(FITBIT_CONFIG_FILE)
    if os.path.isfile(config_path):
        config_file = load_json(config_path)
        if config_file == DEFAULT_CONFIG:
            request_app_setup(
                hass, config, add_entities, config_path, discovery_info=None
            )
            return False
    else:
        save_json(config_path, DEFAULT_CONFIG)
        request_app_setup(hass, config, add_entities, config_path, discovery_info=None)
        return False

    if "fitbit" in _CONFIGURING:
        hass.components.configurator.request_done(_CONFIGURING.pop("fitbit"))

    access_token = config_file.get(ATTR_ACCESS_TOKEN)
    refresh_token = config_file.get(ATTR_REFRESH_TOKEN)
    expires_at = config_file.get(ATTR_LAST_SAVED_AT)
    if None not in (access_token, refresh_token):
        authd_client = Fitbit(
            config_file.get(ATTR_CLIENT_ID),
            config_file.get(ATTR_CLIENT_SECRET),
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            refresh_cb=lambda x: None,
        )

        if int(time.time()) - expires_at > 3600:
            authd_client.client.refresh_token()

        unit_system = config.get(CONF_UNIT_SYSTEM)
        if unit_system == "default":
            authd_client.system = authd_client.user_profile_get()["user"]["locale"]
            if authd_client.system != "en_GB":
                if hass.config.units.is_metric:
                    authd_client.system = "metric"
                else:
                    authd_client.system = "en_US"
        else:
            authd_client.system = unit_system

        dev = []
        registered_devs = authd_client.get_devices()
        clock_format = config.get(CONF_CLOCK_FORMAT)
        for resource in config.get(CONF_MONITORED_RESOURCES):

            # monitor battery for all linked FitBit devices
            if resource == "devices/battery":
                for dev_extra in registered_devs:
                    dev.append(
                        FitbitSensor(
                            authd_client,
                            config_path,
                            resource,
                            hass.config.units.is_metric,
                            clock_format,
                            dev_extra,
                        )
                    )
            else:
                dev.append(
                    FitbitSensor(
                        authd_client,
                        config_path,
                        resource,
                        hass.config.units.is_metric,
                        clock_format,
                    )
                )
        add_entities(dev, True)

    else:
        oauth = FitbitOauth2Client(
            config_file.get(ATTR_CLIENT_ID), config_file.get(ATTR_CLIENT_SECRET)
        )

        redirect_uri = f"{get_url(hass)}{FITBIT_AUTH_CALLBACK_PATH}"

        fitbit_auth_start_url, _ = oauth.authorize_token_url(
            redirect_uri=redirect_uri,
            scope=[
                "activity",
                "heartrate",
                "nutrition",
                "profile",
                "settings",
                "sleep",
                "weight",
            ],
        )

        hass.http.register_redirect(FITBIT_AUTH_START, fitbit_auth_start_url)
        hass.http.register_view(FitbitAuthCallbackView(config, add_entities, oauth))

        request_oauth_completion(hass)


class FitbitAuthCallbackView(HomeAssistantView):
    """Handle OAuth finish callback requests."""

    requires_auth = False
    url = FITBIT_AUTH_CALLBACK_PATH
    name = "api:fitbit:callback"

    def __init__(self, config, add_entities, oauth):
        """Initialize the OAuth callback view."""
        self.config = config
        self.add_entities = add_entities
        self.oauth = oauth

    @callback
    def get(self, request):
        """Finish OAuth callback request."""
        hass = request.app["hass"]
        data = request.query

        response_message = """Fitbit has been successfully authorized!
        You can close this window now!"""

        result = None
        if data.get("code") is not None:
            redirect_uri = f"{get_url(hass)}{FITBIT_AUTH_CALLBACK_PATH}"

            try:
                result = self.oauth.fetch_access_token(data.get("code"), redirect_uri)
            except MissingTokenError as error:
                _LOGGER.error("Missing token: %s", error)
                response_message = f"""Something went wrong when
                attempting authenticating with Fitbit. The error
                encountered was {error}. Please try again!"""
            except MismatchingStateError as error:
                _LOGGER.error("Mismatched state, CSRF error: %s", error)
                response_message = f"""Something went wrong when
                attempting authenticating with Fitbit. The error
                encountered was {error}. Please try again!"""
        else:
            _LOGGER.error("Unknown error when authing")
            response_message = """Something went wrong when
                attempting authenticating with Fitbit.
                An unknown error occurred. Please try again!
                """

        if result is None:
            _LOGGER.error("Unknown error when authing")
            response_message = """Something went wrong when
                attempting authenticating with Fitbit.
                An unknown error occurred. Please try again!
                """

        html_response = f"""<html><head><title>Fitbit Auth</title></head>
        <body><h1>{response_message}</h1></body></html>"""

        if result:
            config_contents = {
                ATTR_ACCESS_TOKEN: result.get("access_token"),
                ATTR_REFRESH_TOKEN: result.get("refresh_token"),
                ATTR_CLIENT_ID: self.oauth.client_id,
                ATTR_CLIENT_SECRET: self.oauth.client_secret,
                ATTR_LAST_SAVED_AT: int(time.time()),
            }
        save_json(hass.config.path(FITBIT_CONFIG_FILE), config_contents)

        hass.async_add_job(setup_platform, hass, self.config, self.add_entities)

        return html_response


class FitbitSensor(Entity):
    """Implementation of a Fitbit sensor."""

    def __init__(
        self, client, config_path, resource_type, is_metric, clock_format, extra=None
    ):
        """Initialize the Fitbit sensor."""
        self.client = client
        self.config_path = config_path
        self.resource_type = resource_type
        self.is_metric = is_metric
        self.clock_format = clock_format
        self.extra = extra
        self._name = FITBIT_RESOURCES_LIST[self.resource_type][0]
        if self.extra:
            self._name = f"{self.extra.get('deviceVersion')} Battery"
        unit_type = FITBIT_RESOURCES_LIST[self.resource_type][1]
        if unit_type == "":
            split_resource = self.resource_type.split("/")
            try:
                measurement_system = FITBIT_MEASUREMENTS[self.client.system]
            except KeyError:
                if self.is_metric:
                    measurement_system = FITBIT_MEASUREMENTS["metric"]
                else:
                    measurement_system = FITBIT_MEASUREMENTS["en_US"]
            unit_type = measurement_system[split_resource[-1]]
        self._unit_of_measurement = unit_type
        self._state = 0

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
        if self.resource_type == "devices/battery" and self.extra:
            battery_level = BATTERY_LEVELS[self.extra.get("battery")]
            return icon_for_battery_level(battery_level=battery_level, charging=None)
        return f"mdi:{FITBIT_RESOURCES_LIST[self.resource_type][2]}"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        attrs[ATTR_ATTRIBUTION] = ATTRIBUTION

        if self.extra:
            attrs["model"] = self.extra.get("deviceVersion")
            attrs["type"] = self.extra.get("type").lower()

        return attrs

    def update(self):
        """Get the latest data from the Fitbit API and update the states."""
        if self.resource_type == "devices/battery" and self.extra:
            self._state = self.extra.get("battery")
        else:
            container = self.resource_type.replace("/", "-")
            response = self.client.time_series(self.resource_type, period="7d")
            raw_state = response[container][-1].get("value")
            if self.resource_type == "activities/distance":
                self._state = format(float(raw_state), ".2f")
            elif self.resource_type == "activities/tracker/distance":
                self._state = format(float(raw_state), ".2f")
            elif self.resource_type == "body/bmi":
                self._state = format(float(raw_state), ".1f")
            elif self.resource_type == "body/fat":
                self._state = format(float(raw_state), ".1f")
            elif self.resource_type == "body/weight":
                self._state = format(float(raw_state), ".1f")
            elif self.resource_type == "sleep/startTime":
                if raw_state == "":
                    self._state = "-"
                elif self.clock_format == "12H":
                    hours, minutes = raw_state.split(":")
                    hours, minutes = int(hours), int(minutes)
                    setting = "AM"
                    if hours > 12:
                        setting = "PM"
                        hours -= 12
                    elif hours == 0:
                        hours = 12
                    self._state = f"{hours}:{minutes:02d} {setting}"
                else:
                    self._state = raw_state
            else:
                if self.is_metric:
                    self._state = raw_state
                else:
                    try:
                        self._state = f"{int(raw_state):,}"
                    except TypeError:
                        self._state = raw_state

        if self.resource_type == "activities/heart":
            self._state = response[container][-1].get("value").get("restingHeartRate")

        token = self.client.client.session.token
        config_contents = {
            ATTR_ACCESS_TOKEN: token.get("access_token"),
            ATTR_REFRESH_TOKEN: token.get("refresh_token"),
            ATTR_CLIENT_ID: self.client.client.client_id,
            ATTR_CLIENT_SECRET: self.client.client.client_secret,
            ATTR_LAST_SAVED_AT: int(time.time()),
        }
        save_json(self.config_path, config_contents)
