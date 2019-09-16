"""Sensor for Livebox router."""
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from . import DOMAIN, SCAN_INTERVAL, DATA_LIVEBOX
from .const import TEMPLATE_SENSOR


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensors."""

    ld = hass.data[DOMAIN][DATA_LIVEBOX]
    id = config_entry.data["id"]
    async_add_entities([RXSensor(ld, id), TXSensor(ld, id)], True)


class LiveboxSensor(Entity):
    """Representation of a livebox sensor."""

    def __init__(self, ld, id):
        """Initialize the sensor."""

        self._ld = ld
        self._box_id = id
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

        self._dsl = await self._ld.async_dsl_status()


class RXSensor(LiveboxSensor):
    """Update the Livebox RxSensor."""

    unit_of_measurement = "Mb/s"

    @property
    def name(self):
        """Return the name of the sensor."""

        return f"{TEMPLATE_SENSOR} download speed"

    @property
    def state(self):
        """Return the state of the device."""

        if self._dsl["DownstreamCurrRate"] is None:
            return None
        return round(self._dsl["DownstreamCurrRate"] / 1000, 2)

    @property
    def unique_id(self):
        """Return unique_id."""

        return f"{self._box_id}_downstream"

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""

        return {
            "downstream_maxrate": self._dsl["DownstreamMaxRate"],
            "downstream_lineattenuation": self._dsl["DownstreamLineAttenuation"],
            "downstream_noisemargin": self._dsl["DownstreamNoiseMargin"],
            "downstream_power": self._dsl["DownstreamPower"],
        }


class TXSensor(LiveboxSensor):
    """Update the Livebox TxSensor."""

    unit_of_measurement = "Mb/s"

    @property
    def name(self):
        """Return the name of the sensor."""

        return f"{TEMPLATE_SENSOR} upload speed"

    @property
    def state(self):
        """Return the state of the device."""

        if self._dsl["UpstreamCurrRate"] is None:
            return None
        return round(self._dsl["UpstreamCurrRate"] / 1000, 2)

    @property
    def unique_id(self):
        """Return unique_id."""

        return f"{self._box_id}_upstream"

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""

        return {
            "upstream_maxrate": self._dsl["UpstreamMaxRate"],
            "upstream_lineattenuation": self._dsl["UpstreamLineAttenuation"],
            "upstream_noisemargin": self._dsl["UpstreamNoiseMargin"],
            "upstream_power": self._dsl["UpstreamPower"],
        }
