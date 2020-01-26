"""Sensor platform for hvv."""
from datetime import datetime, timedelta
import logging

from aiohttp import ClientConnectorError
from pygti.exceptions import InvalidAuth
from pygti.gti import GTI, Auth

from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import DOMAIN, MANUFACTURER

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)
MAX_LIST = 20
MAX_TIME_OFFSET = 360
ICON = "mdi:bus"
UNIT_OF_MEASUREMENT = "min"

ATTR_DEPARTURE = "departure"
ATTR_LINE = "line"
ATTR_ORIGIN = "origin"
ATTR_DIRECTION = "direction"
ATTR_TYPE = "type"
ATTR_ID = "id"
ATTR_DELAY = "delay"
ATTR_NEXT = "next"

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
):  # pylint: disable=unused-argument
    """Set up the sensor platform.

    Skipped, as setup through configuration.yaml is not supported.
    """

    pass


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the sensor platform."""

    session = aiohttp_client.async_get_clientsession(hass)

    sensor = HVVDepartureSensor(hass, config_entry, session)
    async_add_devices([sensor], True)


class HVVDepartureSensor(Entity):
    """HVVDepartureSensor class."""

    def __init__(self, hass, config_entry, session):
        """Initialize."""
        self.hass = hass
        self.config_entry = config_entry
        self.station_name = self.config_entry.data["station"]["name"]
        self.attr = {}
        self._available = False
        self._state = None
        self._name = f"Departures at {self.station_name}"
        self._last_error = None

        self.gti = GTI(
            Auth(
                session,
                self.config_entry.data["username"],
                self.config_entry.data["password"],
                self.config_entry.data["host"],
            )
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, **kwargs):
        """Update the sensor."""

        try:

            departure_time = datetime.now() + timedelta(
                minutes=self.config_entry.options.get("offset", 0)
            )

            payload = {
                "station": self.config_entry.data["station"],
                "time": {
                    "date": departure_time.strftime("%d.%m.%Y"),
                    "time": departure_time.strftime("%H:%M"),
                },
                "maxList": MAX_LIST,
                "maxTimeOffset": MAX_TIME_OFFSET,
                "useRealtime": self.config_entry.options.get("realtime", False),
            }

            if "filter" in self.config_entry.options:
                payload.update({"filter": self.config_entry.options["filter"]})

            data = await self.gti.departureList(payload)

            if data["returnCode"] == "OK" and len(data.get("departures", [])) > 0:

                if self._last_error == ClientConnectorError:
                    _LOGGER.debug("Network available again")

                self._last_error = None

                departure = data["departures"][0]
                self._available = True
                self._state = (
                    departure_time
                    + timedelta(minutes=departure["timeOffset"])
                    + timedelta(seconds=departure.get("delay", 0))
                )

                self.attr[ATTR_LINE] = departure["line"]["name"]
                self.attr[ATTR_ORIGIN] = departure["line"]["origin"]
                self.attr[ATTR_DIRECTION] = departure["line"]["direction"]
                self.attr[ATTR_TYPE] = departure["line"]["type"]["shortInfo"]
                self.attr[ATTR_ID] = departure["line"]["id"]
                self.attr[ATTR_DELAY] = departure.get("delay", 0)

                departures = []
                for departure in data["departures"]:
                    departures.append(
                        {
                            ATTR_DEPARTURE: departure_time
                            + timedelta(minutes=departure["timeOffset"])
                            + timedelta(seconds=departure.get("delay", 0)),
                            ATTR_LINE: departure["line"]["name"],
                            ATTR_ORIGIN: departure["line"]["origin"],
                            ATTR_DIRECTION: departure["line"]["direction"],
                            ATTR_TYPE: departure["line"]["type"]["shortInfo"],
                            ATTR_ID: departure["line"]["id"],
                            ATTR_DELAY: departure.get("delay", 0),
                        }
                    )
                self.attr[ATTR_NEXT] = departures
            else:
                self._available = False

        except InvalidAuth as error:
            if self._last_error != InvalidAuth:
                _LOGGER.error("Authentification failed: %r", error)
                self._last_error = InvalidAuth
            self._available = False
        except ClientConnectorError as error:
            if self._last_error != ClientConnectorError:
                _LOGGER.warn("Network unavailable: %r", error)
                self._last_error = ClientConnectorError

            self._available = False
        except Exception as error:

            if self._last_error != error:
                _LOGGER.error("Error occurred while fetching data: %r", error)
                self._last_error = error

            self._available = False

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        station_id = self.config_entry.data["station"]["id"]
        station_type = self.config_entry.data["station"]["type"]

        return f"{DOMAIN}-{self.config_entry.entry_id}-{station_id}-{station_type}"

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return {
            "identifiers": {
                (
                    DOMAIN,
                    self.config_entry.entry_id,
                    self.config_entry.data["station"]["id"],
                    self.config_entry.data["station"]["type"],
                )
            },
            "name": self.config_entry.data["station"]["name"],
            "manufacturer": MANUFACTURER,
        }

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
        return ICON

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self.attr
