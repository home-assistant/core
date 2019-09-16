"""Sensor for Livebox router."""
import logging

from homeassistant.helpers.entity import Entity

from . import DATA_LIVEBOX, DOMAIN, ID_BOX
from .const import ATTR_SENSORS, TEMPLATE_SENSOR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensors."""
    box_id = hass.data[DOMAIN][ID_BOX]
    bridge = hass.data[DOMAIN][DATA_LIVEBOX]
    async_add_entities(
        [FlowSensor(bridge, box_id, "down"), FlowSensor(bridge, box_id, "up")], True
    )


class FlowSensor(Entity):
    """Representation of a livebox sensor."""

    unit_of_measurement = "Mb/s"

    def __init__(self, device, box_id, flow_direction):
        """Initialize the sensor."""

        self._device = device
        self._box_id = box_id
        self._state = None
        self._dsl = {}
        self._attributs = ATTR_SENSORS[flow_direction]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attributs["name"]

    @property
    def unique_id(self):
        """Return unique_id."""
        cr = self._attributs["current_rate"]
        return f"{self._box_id}_{cr}"

    @property
    def state(self):
        """Return the state of the device."""
        if self._dsl.get(self._attributs["current_rate"]):
            return round(self._dsl[self._attributs["current_rate"]] / 1000, 2)
        return None

    @property
    def device_info(self):
        """Return the device info."""

        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": TEMPLATE_SENSOR,
            "via_device": (DOMAIN, self._box_id),
        }

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        _attributs = {}
        for key, value in self._attributs["attr"].items():
            _attributs[key] = self._dsl.get(value)
        return _attributs

    async def async_update(self):
        """Return update entry."""

        data_status = await self._device.async_get_dsl_status()
        if data_status:
            self._dsl = data_status
