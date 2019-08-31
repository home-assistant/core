# -*- coding: utf-8 -*-
'''
Service for obtaining information about closer bus from Transport Yandex Service
@author: rishatik92@gmail.com
'''

import logging
from datetime import timedelta
from time import time

import voluptuous as vol
from moscow_yandex_transport import YandexMapsRequester

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

STOP_NAME = "Stop name"
USER_AGENT = "Home Assistant"
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

    data = YandexMapsRequester(user_agent=USER_AGENT)
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
