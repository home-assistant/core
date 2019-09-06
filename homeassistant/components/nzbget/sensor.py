"""Monitor the NZBGet API."""
import logging


from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import DATA_NZBGET, DATA_UPDATED, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "NZBGet"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create NZBGet sensors."""
    _LOGGER.info("Setting up NZBGet sensor platform")

    if discovery_info is None:
        return

    nzbget_api = hass.data[DATA_NZBGET]
    monitored_variables = discovery_info["sensors"]
    name = discovery_info["client_name"]

    devices = []
    for ng_type in monitored_variables:
        new_sensor = NZBGetSensor(
            nzbget_api,
            ng_type,
            name,
            SENSOR_TYPES[ng_type][0],
            SENSOR_TYPES[ng_type][1],
        )
        devices.append(new_sensor)

    add_entities(devices, True)


class NZBGetSensor(Entity):
    """Representation of a NZBGet sensor."""

    def __init__(self, api, sensor_type, client_name, sensor_name, unit_of_measurement):
        """Initialize a new NZBGet sensor."""
        self._name = "{} {}".format(client_name, sensor_type)
        self.type = sensor_name
        self.client_name = client_name
        self.api = api
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self.update()
        _LOGGER.debug("Created NZBGet sensor: %s", self.type)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    def update(self):
        """Update state of sensor."""

        if self.api.status is None:
            _LOGGER.debug(
                "Update of %s requested, but no status is available", self._name
            )
            return

        value = self.api.status.get(self.type)
        if value is None:
            _LOGGER.warning("Unable to locate value for %s", self.type)
            return

        if "DownloadRate" in self.type and value > 0:
            # Convert download rate from Bytes/s to MBytes/s
            self._state = round(value / 2 ** 20, 2)
        elif "UpTimeSec" in self.type and value > 0:
            # Convert uptime from seconds to minutes
            self._state = round(value / 60, 2)
        else:
            self._state = value
