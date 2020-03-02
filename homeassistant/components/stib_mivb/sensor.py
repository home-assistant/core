"""Support for STIB-MIVB (Brussels public transport) information."""
import datetime
import logging
import math

from pyodstibmivb import HttpException, ODStibMivb
import pytz
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, DEVICE_CLASS_TIMESTAMP, TIME_MINUTES
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by opendata.stib-mivb.be"

CONF_STOPS = "stops"
CONF_STOP_ID = "stop_id"
CONF_API_KEY = "api_key"
CONF_LANG = "lang"
CONF_MESSAGE_LANG = "message_lang"
CONF_LINE_NUMBERS = "line_numbers"

SUPPORTED_LANGUAGES = ["nl", "fr"]
SUPPORTED_MESSAGE_LANGUAGES = ["en", "nl", "fr"]

TYPES = {
    "0": "tram",
    "1": "subway",
    "3": "bus",
}

STOP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Required(CONF_LINE_NUMBERS): [cv.string],
    }
)

STOPS_SCHEMA = vol.All(cv.ensure_list, [STOP_SCHEMA])

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_LANG): vol.In(SUPPORTED_LANGUAGES),
        vol.Optional(CONF_MESSAGE_LANG): vol.In(SUPPORTED_MESSAGE_LANGUAGES),
        vol.Optional(CONF_STOPS): STOPS_SCHEMA,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Create the sensor."""
    api_key = config[CONF_API_KEY]
    if config[CONF_MESSAGE_LANG]:
        message_lang = config[CONF_MESSAGE_LANG]
    else:
        message_lang = config[CONF_LANG]

    session = async_get_clientsession(hass)

    api = ODStibMivb(api_key, session)

    sensors = []
    for stop in config[CONF_STOPS]:
        sensors.append(
            StibMivbSensor(
                api,
                stop[CONF_STOP_ID],
                stop[CONF_LINE_NUMBERS],
                config[CONF_LANG],
                message_lang,
            )
        )

    async_add_entities(sensors, True)


class StibMivbSensor(Entity):
    """Representation of Stib-Mivb public transport sensor."""

    def __init__(self, api, stop_id, line_ids, lang, message_lang):
        """Initialize the sensor."""
        self.api = api
        self.stop_id = stop_id
        self.line_ids = line_ids
        self.lang = lang
        self.message_lang = message_lang
        self._attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._state = None
        self._stop_name = None
        self._next_passages = None
        self._unit = TIME_MINUTES
        self.__icon = None
        self._attributes["stop_id"] = self.stop_id

    @Throttle(datetime.timedelta(seconds=30))
    async def async_update(self):
        """Get the latest data from the StibMivb API."""
        if self._stop_name is None:
            stop_name = await self.api.get_point_detail(self.stop_id)
            try:
                self._stop_name = stop_name["points"][0]["name"][self.lang]
            except IndexError:
                _LOGGER.error("stop %s does not exist" % self.stop_id)
            self._attributes["stop_name"] = self._stop_name
        self._name = self._stop_name + " line " + " ".join(self.line_ids)

        try:
            waiting_time_response = await self.api.get_waiting_time(self.stop_id)
        except HttpException:
            _LOGGER.error(
                "Http Error getting waiting time for stop %s. %s. %s"(
                    self.stop_id, HttpException, HttpException.text
                )
            )
        try:
            messages_response = await self.api.get_message_by_line(*self.line_ids)
        except HttpException:
            _LOGGER.error(
                "Http Error getting messages for line(s) %s. %s. %s",
                (self.line_ids, HttpException, HttpException.text),
            )
        next_passages = []
        now = pytz.utc.normalize(pytz.utc.localize(datetime.datetime.utcnow()))
        for passing_time in waiting_time_response["points"][0]["passingTimes"]:
            for line_id in self.line_ids:
                if passing_time["lineId"] == line_id:
                    next_passage = {}
                    try:
                        next_passage["next_passing_time"] = passing_time[
                            "expectedArrivalTime"
                        ]
                        next_passage["next_passing_destination"] = passing_time[
                            "destination"
                        ][self.lang]
                        tmp = pytz.utc.normalize(
                            datetime.datetime.fromisoformat(
                                next_passage["next_passing_time"]
                            )
                        )
                        next_passage["waiting_time"] = round(
                            (tmp - now).total_seconds() / 60
                        )

                    except KeyError:
                        _LOGGER.debug(
                            "No arrivaltime for line %s, might be end of service",
                            line_id,
                        )
                        try:
                            next_passage["next_passing_message"] = passing_time[
                                "message"
                            ][self.lang]
                        except KeyError:
                            _LOGGER.error(
                                "No arrivaltime and no message for line %s", line_id
                            )
                    line_name = await self.api.get_line_long_name(line_id)
                    if self.lang == "nl":
                        try:
                            line_name = await self.api.get_translation_nl(line_name)
                        except KeyError:
                            _LOGGER.warning("No translation found for %s", line_name)

                    next_passage["line_number"] = line_id
                    next_passage["line_name"] = line_name

                    messages = []
                    for message in messages_response["messages"]:
                        for line in message["lines"]:
                            if line["id"] == line_id:
                                for stop in message["points"]:
                                    if stop["id"] == self.stop_id:
                                        messages.append(
                                            message["content"][0]["text"][0][self.lang]
                                        )
                    type = await self.api.get_line_type(line_id)
                    next_passage["messages"] = messages
                    next_passage["line_type"] = TYPES[type]
                    next_passage["line_color"] = await self.api.get_line_color(line_id)
                    next_passage[
                        "line_text_color"
                    ] = await self.api.get_line_text_color(line_id)

                    next_passages.append(next_passage)
        self._next_passages = sorted(
            next_passages, key=lambda i: i.get("waiting_time", math.inf)
        )
        self._attributes["line_name"] = self._next_passages[0]["line_name"]
        self._attributes["line_type"] = self._next_passages[0]["line_type"]
        self._attributes["line_color"] = self._next_passages[0]["line_color"]
        self._attributes["line_text_color"] = self._next_passages[0]["line_text_color"]
        self._attributes["messages"] = self._next_passages[0]["messages"]
        self._attributes["next_passages"] = self._next_passages
        if self._next_passages[0].get("next_passing_time"):
            self._state = self._next_passages[0]["next_passing_time"]
            self.__icon = f"mdi:{next_passages[0]['line_type']}"
        else:
            self._state = self._next_passages[0].get("next_passing_message")
            self.__icon = "mdi:bus-alert"

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self.__icon

    @property
    def device_state_attributes(self):
        """Return attributes for the sensor."""
        return self._attributes
