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
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    client_id = config.get(CONF_CLIENT_ID)
    client_secret = config.get(CONF_CLIENT_SECRET)
    time_zone = str(hass.config.time_zone)
    name = config.get(CONF_NAME)

    flume_devices = FlumeAuth(username, password, client_id, client_secret)

    try:
        for device in flume_devices._devices:
            if device["type"] == FLUME_TYPE_SENSOR:
                flume = FlumeData(
                    username,
                    password,
                    client_id,
                    client_secret,
                    device["id"],
                    time_zone,
                    SCAN_INTERVAL,
                )
                add_entities([FlumeSensor(flume, f"{name} {device['id']}")], True)
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
        self._unit_of_measurement = "GALLONS"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

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
        self._token = self.getToken()
        self._user_id = self.getUserId()
        self._bearer = self.getBearer()
        self._devices = self.getDevices()

    def getToken(self):
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

        if response.status_code == 200:
            return json.loads(response.text)["data"]
        else:
            raise Exception(
                "Can't get token for user {}. Response code returned : {}".format(
                    self._username, response.status_code
                )
            )

    def getUserId(self):
        """Return User ID for authorized user."""
        json_token_data = self._token[0]
        return json.loads(
            base64.b64decode(json_token_data["access_token"].split(".")[1])
        )["user_id"]

    def getBearer(self):
        """Return Bearer for Authorized session."""
        return self._token[0]["access_token"]

    def getDevices(self):
        """Return all available devices from Flume API."""
        url = "https://api.flumetech.com/users/" + str(self._user_id) + "/devices"
        querystring = {"user": "false", "location": "false"}
        headers = {"authorization": "Bearer " + self._bearer + ""}
        response = requests.request("GET", url, headers=headers, params=querystring)

        _LOGGER.debug("getDevices Response: %s", response.text)

        if response.status_code == 200:
            return json.loads(response.text)["data"]
        else:
            raise Exception(
                "Impossible to retreive devices. Response code returned : {}".format(
                    response.status_code
                )
            )


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

        queryDict = {
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
        response = requests.post(url, json=queryDict, headers=headers)

        _LOGGER.debug("Update URL: %s", url)
        _LOGGER.debug("Update headers: %s", headers)
        _LOGGER.debug("Update queryDict: %s", queryDict)
        _LOGGER.debug("Update Response: %s", response.text)

        if response.status_code == 200:
            self.value = json.loads(response.text)["data"][0]["update"][0]["value"]
        else:
            raise Exception(
                "Can't update flume data for user id {}. Response code returned : {}".format(
                    self._username, response.status_code
                )
            )
