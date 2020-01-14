"""Support for OpenUV sensors."""
import logging

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from .const import CONF_METER_ID, SENSOR_TYPES
from . import TauronAmiplusSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up an TAURON sensor based on existing config."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a TAURON sensor based on a config entry."""
    user = (entry.data[CONF_USERNAME],)
    password = (entry.data[CONF_PASSWORD],)
    meter_id = (entry.data[CONF_METER_ID],)
    sensors = []
    for sensor_type in SENSOR_TYPES:
        # name, interval, unit, = SENSOR_TYPES[sensor_type]
        sensors.append(TauronSensor(user, password, meter_id, sensor_type))

    async_add_entities(sensors, True)


class TauronSensor(TauronAmiplusSensor):
    """Define a sensor for TAURON."""

    def __init__(self, user, password, meter_id, sensor_type):
        """Initialize the sensor."""
        super().__init__(user, password, meter_id, sensor_type)
