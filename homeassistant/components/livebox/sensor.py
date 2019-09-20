"""Sensor for Livebox router."""
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from . import DOMAIN, SCAN_INTERVAL, DATA_LIVEBOX
from .const import TEMPLATE_SENSOR


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensors."""

    box_data = hass.data[DOMAIN][DATA_LIVEBOX]
    box_id = config_entry.data["id"]
    async_add_entities([RXSensor(box_data, box_id), TXSensor(box_data, box_id)], True)


class LiveboxSensor(Entity):
    """Representation of a livebox sensor."""

    def __init__(self, box_data, box_id):
        """Initialize the sensor."""

        self._box_data = box_data
        self._box_id = box_id
        self._state = None
        self._dsl = {}

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

        data_status = await self._box_data.async_dsl_status()
        if data_status:
            self._dsl = data_status


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

        if self._dsl.get("DownstreamCurrRate"):
            return round(self._dsl["DownstreamCurrRate"] / 1000, 2)
        return None

    @property
    def unique_id(self):
        """Return unique_id."""

        return f"{self._box_id}_downstream"

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""

        return {
            "downstream_maxrate": self._dsl.get("DownstreamMaxRate", None),
            "downstream_lineattenuation": self._dsl.get(
                "DownstreamLineAttenuation", None
            ),
            "downstream_noisemargin": self._dsl.get("DownstreamNoiseMargin", None),
            "downstream_power": self._dsl.get("DownstreamPower", None),
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

        if self._dsl.get("UpstreamCurrRate"):
            return round(self._dsl["UpstreamCurrRate"] / 1000, 2)
        return None

    @property
    def unique_id(self):
        """Return unique_id."""

        return f"{self._box_id}_upstream"

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""

        return {
            "upstream_maxrate": self._dsl.get("UpstreamMaxRate", None),
            "upstream_lineattenuation": self._dsl.get("UpstreamLineAttenuation", None),
            "upstream_noisemargin": self._dsl.get("UpstreamNoiseMargin", None),
            "upstream_power": self._dsl.get("UpstreamPower", None),
        }
