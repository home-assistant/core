"""Support for OPNsense sensors."""
from datetime import timedelta
import logging

from pyopnsense.exceptions import APIException
from requests.exceptions import ConnectionError as requestsConnectionError

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.helpers.entity import Entity, async_generate_entity_id

from .const import (
    CONF_GATEWAY,
    OPNSENSE_DATA,
    SENSOR_GATEWAY_STATUS,
    SENSOR_SCAN_INTERVAL_SECS,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=SENSOR_SCAN_INTERVAL_SECS)
# Sensor types are defined like: API client, Name, units, icon
SENSORS = {
    SENSOR_GATEWAY_STATUS: ["gateways", "gateway", None, "mdi:wan"],
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a sensor for an OPNsense router."""
    if discovery_info is None:
        return

    if discovery_info.get(CONF_GATEWAY):
        async_add_entities(
            [
                OPNsenseSensor(hass, gateway_sensor, SENSOR_GATEWAY_STATUS)
                for gateway_sensor in discovery_info[CONF_GATEWAY]
            ],
            True,
        )


class OPNsenseSensor(Entity):
    """A sensor implementation for OPNsense gateway status."""

    def __init__(self, hass, sensor, sensor_type):
        """Initialize a sensor for OPNsense gateway status."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{SENSORS[sensor_type][1]}_{sensor}", hass=hass
        )
        self._name = sensor
        self._sensor_type = sensor_type
        self._client = hass.data[OPNSENSE_DATA][SENSORS[sensor_type][0]]
        self._state = None
        self._attrs = {}
        self._availability = None
        self._icon = SENSORS[sensor_type][3]
        self._unit_of_measurement = SENSORS[sensor_type][2]

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self.entity_id

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Return True if entity is available."""
        return self._availability

    def update(self):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Updating %s sensor", self._name)

        try:
            if self._sensor_type == SENSOR_GATEWAY_STATUS:
                status = self._client.status()["items"]
                for gateway in status:
                    if gateway["name"] == self._name:
                        self._state = gateway["status_translated"]
                        self._attrs = {
                            k: gateway[k]
                            for k in gateway
                            if k not in ("name", "status_translated")
                        }

            self._availability = True

        except (APIException, requestsConnectionError):
            self._availability = False
