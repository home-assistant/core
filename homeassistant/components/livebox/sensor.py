"""Sensor for Livebox router."""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from . import DOMAIN, SCAN_INTERVAL
from .const import TEMPLATE_SENSOR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensors."""
    box = hass.data[DOMAIN]
    async_add_entities([RXSensor(box, config_entry), TXSensor(box, config_entry)], True)


class LiveboxSensor(Entity):
    """Representation of a livebox sensor."""

    def __init__(self, box, config_entry):
        """Initialize the sensor."""

        self._box = box
        self._box_id = config_entry.data["box_id"]
        self._state = None
        self._datas = None
        self._dsl = None

    @property
    def device_info(self):
        """Return the device info."""

        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": "Orange",
            "via_device": (DOMAIN, self._box_id),
        }

    @Throttle(SCAN_INTERVAL)
    async def async_update(self):
        """Return update entry."""


class RXSensor(LiveboxSensor):
    """Update the Livebox RxSensor."""

    unit_of_measurement = "Mb/s"

    @property
    def name(self):
        """Return the name of the sensor."""

        return TEMPLATE_SENSOR.format("download speed")

    @property
    def state(self):
        """Return the state of the device."""

        if self._dsl["DownstreamCurrRate"] is None:
            return None
        return round(self._dsl["DownstreamCurrRate"] / 1000, 2)

    @property
    def unique_id(self):
        """Return unique_id."""

        return "{}_downstream".format(self._box_id)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""

        return {
            "downstream_maxrate": self._dsl["DownstreamMaxRate"],
            "downstream_lineattenuation": self._dsl["DownstreamLineAttenuation"],
            "downstream_noisemargin": self._dsl["DownstreamNoiseMargin"],
            "downstream_power": self._dsl["DownstreamPower"],
        }

    async def async_update(self):
        """Get the value from fetched datas."""

        parameters = {"parameters": {"mibs": "dsl", "flag": "", "traverse": "down"}}
        self._datas = await self._box.connection.get_data_MIBS(parameters)
        self._dsl = self._datas["status"]["dsl"]["dsl0"]


class TXSensor(LiveboxSensor):
    """Update the Livebox TxSensor."""

    unit_of_measurement = "Mb/s"

    @property
    def name(self):
        """Return the name of the sensor."""

        return TEMPLATE_SENSOR.format("upload speed")

    @property
    def state(self):
        """Return the state of the device."""

        if self._dsl["UpstreamCurrRate"] is None:
            return None
        return round(self._dsl["UpstreamCurrRate"] / 1000, 2)

    @property
    def unique_id(self):
        """Return unique_id."""

        return "{}_upstream".format(self._box_id)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""

        return {
            "upstream_maxrate": self._dsl["UpstreamMaxRate"],
            "upstream_lineattenuation": self._dsl["UpstreamLineAttenuation"],
            "upstream_noisemargin": self._dsl["UpstreamNoiseMargin"],
            "upstream_power": self._dsl["UpstreamPower"],
        }

    async def async_update(self):
        """Get the value from fetched datas."""
        parameters = {"parameters": {"mibs": "dsl", "flag": "", "traverse": "down"}}
        self._datas = await self._box.connection.get_data_MIBS(parameters)
        self._dsl = self._datas["status"]["dsl"]["dsl0"]
