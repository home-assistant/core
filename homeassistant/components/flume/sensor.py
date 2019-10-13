"""Sensor for displaying the number of result from Flume."""
import base64
from datetime import datetime, timedelta
import json
import logging

import pytz
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Flume Sensor"

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
FLUME_TYPE_SENSOR = 2

SCAN_INTERVAL = timedelta(minutes=1)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Flume sensor."""
    _username = config[CONF_USERNAME]
    _password = config[CONF_PASSWORD]
    _client_id = config[CONF_CLIENT_ID]
    _client_secret = config[CONF_CLIENT_SECRET]
    time_zone = str(hass.config.time_zone)
    name = config[CONF_NAME]

    flume_devices = FlumeAuth(_username, _password, _client_id, _client_secret)

    # noinspection PyBroadException
    try:
        for device in flume_devices.device_list:
            if device["type"] == FLUME_TYPE_SENSOR:
                flume = FlumeData(
                    _username,
                    _password,
                    _client_id,
                    _client_secret,
                    device["id"],
                    time_zone,
                    SCAN_INTERVAL,
                )
                add_entities([FlumeSensor(flume, f"{name} {device['id']}")], True)
    except KeyError:
        _LOGGER.error("No Flume Devices Returned of Type: %s", FLUME_TYPE_SENSOR)
        return False
    except Exception as error:
        _LOGGER.error("Unable to setup Flume Devices: %s", error)
        return False


class FlumeSensor(Entity):
    """Representation of the Flume sensor."""

    def __init__(self, flume, name):
        """Initialize the Flume sensor."""
        self.flume = flume
        self._name = name
        self._state = None

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
        """Return the unit the value is expressed in."""
        return "gal"

    def update(self):
        """Get the latest data and updates the states."""
        self.flume.update()
        self._state = self.flume.value


class FlumeAuth:
    """Get the Authentication Bearer, User ID and list of devices from Flume API."""

    def __init__(self, username, password, client_id, client_secret):
        """Initialize the data object."""
        self._username = username
        self._password = password
        self._client_id = client_id
        self._client_secret = client_secret
        self._token = self.get_token()
        self._user_id = self.get_userid()
        self._bearer = self.get_bearer()
        self.device_list = self.get_devices()

    def get_token(self):
        """Return authorization token for session."""
        url = "https://api.flumetech.com/oauth/token"
        payload = (
            '{"grant_type":"password","client_id":"'
            + self._client_id
            + '","client_secret":"'
            + self._client_secret
            + '","username":"'
            + self._username
            + '","password":"'
            + self._password
            + '"}'
        )
        headers = {"content-type": "application/json"}

        response = requests.request("POST", url, data=payload, headers=headers)

        _LOGGER.debug("Token Payload: %s", payload)
        _LOGGER.debug("Token Response: %s", response.text)

        if response.status_code != 200:
            raise Exception(
                "Can't get token for user {}. Response code returned : {}".format(
                    self._username, response.status_code
                )
            )

        return json.loads(response.text)["data"]

    def get_userid(self):
        """Return User ID for authorized user."""
        json_token_data = self._token[0]
        return json.loads(
            base64.b64decode(json_token_data["access_token"].split(".")[1])
        )["user_id"]

    def get_bearer(self):
        """Return Bearer for Authorized session."""
        return self._token[0]["access_token"]

    def get_devices(self):
        """Return all available devices from Flume API."""
        url = "https://api.flumetech.com/users/" + str(self._user_id) + "/devices"
        querystring = {"user": "false", "location": "false"}
        headers = {"authorization": "Bearer " + self._bearer + ""}
        response = requests.request("GET", url, headers=headers, params=querystring)

        _LOGGER.debug("get_devices Response: %s", response.text)

        if response.status_code != 200:
            raise Exception(
                "Impossible to retreive devices. Response code returned : {}".format(
                    response.status_code
                )
            )

        return json.loads(response.text)["data"]


class FlumeData:
    """Get the latest data and update the states."""

    def __init__(
        self,
        username,
        password,
        client_id,
        client_secret,
        device_id,
        time_zone,
        scan_interval,
    ):
        """Initialize the data object."""
        self._username = username
        self._device_id = device_id
        self._scan_interval = scan_interval
        self._time_zone = time_zone
        self.value = None

        flume_auth = FlumeAuth(username, password, client_id, client_secret)

        self._user_id = flume_auth._user_id
        self._bearer = flume_auth._bearer
        self.update()

    def update(self):
        """Return updated value for session."""
        url = (
            "https://api.flumetech.com/users/"
            + str(self._user_id)
            + "/devices/"
            + str(self._device_id)
            + "/query"
        )

        utc_now = pytz.utc.localize(datetime.utcnow())
        time_zone_now = utc_now.astimezone(pytz.timezone(self._time_zone))

        since_datetime = (time_zone_now - self._scan_interval).strftime(
            "%Y-%m-%d %H:%M:00"
        )
        until_datetime = time_zone_now.strftime("%Y-%m-%d %H:%M:00")

        query_dict = {
            "queries": [
                {
                    "since_datetime": since_datetime,
                    "until_datetime": until_datetime,
                    "bucket": "MIN",
                    "request_id": "update",
                    "units": "GALLONS",
                }
            ]
        }

        headers = {"authorization": "Bearer " + self._bearer + ""}
        response = requests.post(url, json=query_dict, headers=headers)

        _LOGGER.debug("Update URL: %s", url)
        _LOGGER.debug("Update headers: %s", headers)
        _LOGGER.debug("Update query_dict: %s", query_dict)
        _LOGGER.debug("Update Response: %s", response.text)

        if response.status_code != 200:
            raise Exception(
                "Can't update flume data for user id {}. Response code returned : {}".format(
                    self._username, response.status_code
                )
            )

        self.value = json.loads(response.text)["data"][0]["update"][0]["value"]
