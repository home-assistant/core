# -*- coding: utf-8 -*-
'''
Service for obtaining information about closer bus from Transport Yandex Service
@author: rishatik92@gmail.com
'''

RESOURCE = 'https://yandex.ru/maps/api/masstransit/getStopInfo'
CONFIG = {
    'init_url': 'https://maps.yandex.ru',
    'uri': RESOURCE,
    'params': {'ajax': 1, 'lang': 'en', 'locale': 'en_EN', 'mode': 'prognosis'},
    'headers': {'User-Agent': "Home Assistant"}}
SESSION_KEY = "sessionId"
CSRF_TOKEN_KEY = "csrfToken"
import logging
import re
from datetime import timedelta
from json import loads
from time import time

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

STOP_NAME = "Stop name"

ATTRIBUTION = "Data provided by maps.yandex.ru"

CONF_STOP_ID = "stop_id"
CONF_ROUTE = "routes"

DEFAULT_NAME = "Yandex Transport"
ICON = "mdi:bus"

SCAN_INTERVAL = timedelta(minutes=1)
TIME_STR_FORMAT = "%H:%M"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_ROUTE, default=[]): cv.ensure_list,
    }
)


def due_in_minutes(timestamp: int):
    """Get the time in minutes from a timestamp.

    The timestamp should be in the posix time
    """
    diff = timestamp - time()
    if diff < 0:
        diff = 0

    return str(int(diff / 60))


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Yandex transport sensor."""
    stop_id = config.get(CONF_STOP_ID)
    name = config.get(CONF_NAME)
    routes = config.get(CONF_ROUTE)

    data = YandexMapsRequester(CONFIG)
    add_entities([DiscoverMoscowYandexTransport(data, stop_id, routes, name)], True)


class DiscoverMoscowYandexTransport(Entity):
    def __init__(self, requester, stop_id, routes, name):
        """

        :type requester: data provider for request to yandex api
        """
        self.requester = requester
        self._stop_id = stop_id
        self._routes = []
        for route in routes:
            self._routes.append(str(route))
        self._state = None
        self._name = name
        self._attrs = None
        self._next_route = None

    def update(self):
        """Get the latest data from maps.yandex.ru and update the states."""
        result = {}
        closer_time = None
        try:
            yandex_reply = self.requester.get_stop_info(self._stop_id)
            data = yandex_reply["data"]
            stop_metadata = data["properties"]["StopMetaData"]
        except KeyError as e:
            _LOGGER.warning(f"Exception KeyError was captured, missing key is {e}. Yandex returned :{yandex_reply}")
            self.requester.set_new_session()
            data = self.requester.get_stop_info(self._stop_id)["data"]
            stop_metadata = data["properties"]["StopMetaData"]
        stop_name = data["properties"]["name"]
        transport_list = stop_metadata["Transport"]
        for transport in transport_list:
            route = transport["name"]
            if self._routes and route not in self._routes:
                # skip unnecessary route info
                continue
            if "Events" in transport["BriefSchedule"]:
                for event in transport["BriefSchedule"]["Events"]:
                    if "Estimated" in event:
                        posix_time_next = int(event["Estimated"]["value"])
                        if closer_time is None or closer_time > posix_time_next:
                            closer_time = posix_time_next
                        if route not in result:
                            result[route] = []
                        result[route].append(event["Estimated"]["text"])
        for route in result:
            result[route] = ", ".join(result[route])
        result[STOP_NAME] = stop_name
        result[ATTR_ATTRIBUTION] = ATTRIBUTION
        if closer_time is None:
            self._state = "n/a"
        else:
            self._state = due_in_minutes(closer_time)
        self._attrs = result

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "min"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON


class YandexMapsRequester(object):
    def __init__(self, config):
        self._config = config
        self.set_new_session()

    def get_stop_info(self, stop_id):
        """"
        get transport data for stop_id in json
        """
        self._config["params"]["id"] = f"stop__{stop_id}"
        req = requests.get(self._config["uri"], params=self._config["params"], cookies=self._config["cookies"],
                           headers=self._config["headers"])
        return loads(req.content.decode('utf8'))

    def set_new_session(self):
        """
        Create new http session to Yandex, with valid csrf_token and session_id
        """
        ya_request = requests.get(url=self._config["init_url"], headers=self._config["headers"])
        reply = ya_request.content.decode('utf8')
        self._config["params"][CSRF_TOKEN_KEY] = re.search(f'"{CSRF_TOKEN_KEY}":"(\w+.\w+)"', reply).group(1)
        self._config["cookies"] = dict(ya_request.cookies)
        self._config["params"][SESSION_KEY] = re.search(f'"{SESSION_KEY}":"(\d+.\d+)"', reply).group(1)
