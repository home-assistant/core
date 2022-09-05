"""Sensor platform for hvv."""
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientConnectorError
from pygti.exceptions import InvalidAuth

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle
from homeassistant.util.dt import get_time_zone, utcnow

from .const import ATTRIBUTION, CONF_STATION, DOMAIN, MANUFACTURER

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)
MAX_LIST = 20
MAX_TIME_OFFSET = 360
ICON = "mdi:bus"

ATTR_DEPARTURE = "departure"
ATTR_LINE = "line"
ATTR_ORIGIN = "origin"
ATTR_DIRECTION = "direction"
ATTR_TYPE = "type"
ATTR_DELAY = "delay"
ATTR_NEXT = "next"

PARALLEL_UPDATES = 0
BERLIN_TIME_ZONE = get_time_zone("Europe/Berlin")

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    hub = hass.data[DOMAIN][config_entry.entry_id]

    session = aiohttp_client.async_get_clientsession(hass)

    sensor = HVVDepartureSensor(hass, config_entry, session, hub)
    async_add_devices([sensor], True)


class HVVDepartureSensor(SensorEntity):
    """HVVDepartureSensor class."""

    def __init__(self, hass, config_entry, session, hub):
        """Initialize."""
        self.config_entry = config_entry
        self.station_name = self.config_entry.data[CONF_STATION]["name"]
        self.attr = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._available = False
        self._state = None
        self._name = f"Departures at {self.station_name}"
        self._last_error = None

        self.gti = hub.gti

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, **kwargs: Any) -> None:
        """Update the sensor."""
        departure_time = utcnow() + timedelta(
            minutes=self.config_entry.options.get("offset", 0)
        )

        departure_time_tz_berlin = departure_time.astimezone(BERLIN_TIME_ZONE)

        payload = {
            "station": self.config_entry.data[CONF_STATION],
            "time": {
                "date": departure_time_tz_berlin.strftime("%d.%m.%Y"),
                "time": departure_time_tz_berlin.strftime("%H:%M"),
            },
            "maxList": MAX_LIST,
            "maxTimeOffset": MAX_TIME_OFFSET,
            "useRealtime": self.config_entry.options.get("realtime", False),
        }

        if "filter" in self.config_entry.options:
            payload.update({"filter": self.config_entry.options["filter"]})

        try:
            data = await self.gti.departureList(payload)
        except InvalidAuth as error:
            if self._last_error != InvalidAuth:
                _LOGGER.error("Authentication failed: %r", error)
                self._last_error = InvalidAuth
            self._available = False
        except ClientConnectorError as error:
            if self._last_error != ClientConnectorError:
                _LOGGER.warning("Network unavailable: %r", error)
                self._last_error = ClientConnectorError
            self._available = False
        except Exception as error:  # pylint: disable=broad-except
            if self._last_error != error:
                _LOGGER.error("Error occurred while fetching data: %r", error)
                self._last_error = error
            self._available = False

        if not (data["returnCode"] == "OK" and data.get("departures")):
            self._available = False
            return

        if self._last_error == ClientConnectorError:
            _LOGGER.debug("Network available again")

        self._last_error = None

        departure = data["departures"][0]
        line = departure["line"]
        delay = departure.get("delay", 0)
        self._available = True
        self._state = (
            departure_time
            + timedelta(minutes=departure["timeOffset"])
            + timedelta(seconds=delay)
        )

        self.attr.update(
            {
                ATTR_LINE: line["name"],
                ATTR_ORIGIN: line["origin"],
                ATTR_DIRECTION: line["direction"],
                ATTR_TYPE: line["type"]["shortInfo"],
                ATTR_ID: line["id"],
                ATTR_DELAY: delay,
            }
        )

        departures = []
        for departure in data["departures"]:
            line = departure["line"]
            delay = departure.get("delay", 0)
            departures.append(
                {
                    ATTR_DEPARTURE: departure_time
                    + timedelta(minutes=departure["timeOffset"])
                    + timedelta(seconds=delay),
                    ATTR_LINE: line["name"],
                    ATTR_ORIGIN: line["origin"],
                    ATTR_DIRECTION: line["direction"],
                    ATTR_TYPE: line["type"]["shortInfo"],
                    ATTR_ID: line["id"],
                    ATTR_DELAY: delay,
                }
            )
        self.attr[ATTR_NEXT] = departures

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        station_id = self.config_entry.data[CONF_STATION]["id"]
        station_type = self.config_entry.data[CONF_STATION]["type"]

        return f"{self.config_entry.entry_id}-{station_id}-{station_type}"

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self.config_entry.entry_id,
                    self.config_entry.data[CONF_STATION]["id"],
                    self.config_entry.data[CONF_STATION]["type"],
                )
            },
            manufacturer=MANUFACTURER,
            name=self._name,
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SensorDeviceClass.TIMESTAMP

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self.attr
