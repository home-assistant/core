"""Sensor platform for hvv."""
from datetime import datetime, timedelta
import logging

from pygti.gti import GTI

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import DOMAIN

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)
MAX_LIST = 5
MAX_TIME_OFFSET = 200
ICON = "mdi:bus"
UNIT_OF_MEASUREMENT = "min"

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
):  # pylint: disable=unused-argument
    """Set up the sensor platform."""
    # async_add_entities([HVVDepartureSensor(hass, discovery_info)], True)
    pass


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the sensor platform."""

    data = HVVDepartureData(hass, config_entry)

    async_add_devices([HVVDepartureSensor(hass, config_entry, data)], True)


class HVVDepartureSensor(Entity):
    """HVVDepartureSensor class."""

    def __init__(self, hass, entry, data):
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.config = self.entry.data
        self.station_name = self.config["station"]["name"]
        self.data = data
        self.attr = {}
        self._state = None
        self._name = f"Departures at {self.station_name}"

    async def async_update(self):
        """Update the sensor."""

        self.data.update()

        if (
            self.data.data["returnCode"] == "OK"
            and len(self.data.data["departures"]) > 0
        ):
            departure = self.data.data["departures"][0]
            self._state = departure["timeOffset"] + departure.get("delay", 0) // 60

            self.attr["line"] = departure["line"]["name"]
            self.attr["origin"] = departure["line"]["origin"]
            self.attr["direction"] = departure["line"]["direction"]
            self.attr["type"] = departure["line"]["type"]["shortInfo"]
            self.attr["id"] = departure["line"]["id"]

            if len(self.data.data["departures"]) > 1:
                departures = []
                for departure in self.data.data["departures"][1:]:
                    departures.append(
                        {
                            "departure": departure["timeOffset"]
                            + departure.get("delay", 0) // 60,
                            "line": departure["line"]["name"],
                            "origin": departure["line"]["origin"],
                            "direction": departure["line"]["direction"],
                            "type": departure["line"]["type"]["shortInfo"],
                            "id": departure["line"]["id"],
                        }
                    )
                self.attr["next"] = departures
        else:
            self._state = None
            self.attr = {}

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        station_id = self.config["station"]["id"]
        station_type = self.config["station"]["type"]

        return f"{DOMAIN}-{self.entry.entry_id}-{station_id}-{station_type}"

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return {
            "identifiers": {
                (
                    DOMAIN,
                    self.entry.entry_id,
                    self.config["station"]["id"],
                    self.config["station"]["type"],
                )
            },
            "name": self.config["station"]["name"],
            "manufacturer": "HVV",
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
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return UNIT_OF_MEASUREMENT

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self.attr


class HVVDepartureData:
    """Get the latest data and update the states."""

    def __init__(self, hass, entry):
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.config = self.entry.data
        self.last_update = None
        self.gti = GTI(
            self.config["username"], self.config["password"], self.config["host"]
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the HVV departure data."""

        try:

            payload = {
                "station": self.config["station"],
                "time": {"date": "heute", "time": "jetzt"},
                "maxList": MAX_LIST,
                "maxTimeOffset": MAX_TIME_OFFSET,
                "useRealtime": self.config["realtime"],
                "filter": self.config["filter"],
            }

            self.data = self.gti.departureList(payload)

            self.last_update = datetime.today().strftime("%Y-%m-%d %H:%M")
        except Exception as error:
            _LOGGER.error("Error occurred while fetching data: %r", error)
            self.data = None
            return False
