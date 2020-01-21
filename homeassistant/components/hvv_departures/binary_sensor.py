"""Sensor platform for hvv."""
from datetime import datetime, timedelta
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorDevice,
)
from homeassistant.util import Throttle

from .const import DOMAIN, ICON_ELEVATOR

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
):  # pylint: disable=unused-argument
    """Set up the sensor platform."""
    pass


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the sensor platform."""

    data = HVVElevatorData(hass, config_entry)

    devices = []

    if "partialStations" in config_entry.data["stationInformation"]:
        for partial_station in config_entry.data["stationInformation"][
            "partialStations"
        ]:
            if "elevators" in partial_station:
                for elevator in partial_station["elevators"]:
                    devices.append(
                        HVVElevatorBinarySensor(
                            hass,
                            config_entry.data,
                            data,
                            elevator.get("lines", []),
                            elevator["label"],
                            elevator["description"],
                        )
                    )

    async_add_devices(devices)


class HVVElevatorBinarySensor(BinarySensorDevice):
    """HVV elevator binary sensor class."""

    def __init__(self, hass, config, data, lines, label, description):
        """Inizialize."""
        self.hass = hass
        self.config = config
        self.data = data
        self.lines = lines
        self.label = label
        self.station_name = self.config["station"]["name"]
        self.attr = {}
        self._status = None
        self._name = f"Aufzug {self.station_name}, {description}"

    async def async_update(self):
        """Update the sensor."""

        self.data.update()

        if self.data.data["returnCode"] == "OK":

            elevator = self.data.get_elevator(self.lines, self.label)

            self._status = elevator["state"] == "OUTOFORDER"
            self.attr["cabin width"] = elevator["cabinWidth"]
            self.attr["cabin length"] = elevator["cabinLength"]
            self.attr["door width"] = elevator["doorWidth"]
            self.attr["type"] = elevator["elevatorType"]
            self.attr["buttons"] = elevator["buttonType"]
            self.attr["cause"] = elevator["cause"] if "cause" in elevator else None

        else:
            self._status = None
            self.attr = {}

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""

        lines = "-".join(self.lines)

        return f"{self.label}-{self.station_name}-{lines}"

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return {
            "identifiers": {
                (DOMAIN, self.config["station"]["id"], self.config["station"]["type"])
            },
            "name": self.config["station"]["name"],
            "manufacturer": "HVV",
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this binary_sensor."""
        return DEVICE_CLASS_PROBLEM

    @property
    def is_on(self):
        """Return true if the binary_sensor is on."""
        return self._status

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_ELEVATOR

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self.attr


class HVVElevatorData:
    """Get the latest data and update the states."""

    def __init__(self, hass, entry):
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.config = self.entry.data
        self.last_update = None
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update hvv station data."""

        try:
            self.data = self.hass.data[DOMAIN][self.entry.entry_id].stationInformation(
                {"station": self.config["station"]}
            )
            self.last_update = datetime.today().strftime("%Y-%m-%d %H:%M")
        except Exception as error:
            _LOGGER.error("Error occurred while fetching data: %r", error)
            self.data = None
            return False

    def get_elevator(self, lines, label):
        """Get the elevator from the data by lines and label."""

        for partial_station in self.data["partialStations"]:
            if "elevators" in partial_station:
                for elevator in partial_station["elevators"]:

                    elevator_lines = elevator["lines"] if "lines" in elevator else []

                    if elevator["label"] == label and elevator_lines == lines:
                        return elevator
        return None
