"""Support for OpenUV sensors."""
import logging

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from . import TauronAmiplusSensor
from .const import CONF_METER_ID, CONF_SHOW_GENERATION, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up an TAURON sensor based on existing config."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a TAURON sensor based on a config entry."""
    user = (entry.data[CONF_USERNAME],)
    password = (entry.data[CONF_PASSWORD],)
    meter_id = (entry.data[CONF_METER_ID],)
    show_generation_sensors = True
    if CONF_SHOW_GENERATION in entry.data:
        show_generation_sensors = (entry.data[CONF_SHOW_GENERATION],)
    sensors = []
    for sensor_type in SENSOR_TYPES:
        generation = True if "generation" == SENSOR_TYPES[sensor_type][3][0] else False
        if generation is False or show_generation_sensors:
            sensor_name = SENSOR_TYPES[sensor_type][4]
            sensors.append(
                TauronSensor(
                    sensor_name,
                    user,
                    password,
                    meter_id,
                    generation,
                    sensor_type,
                )
            )

    async_add_entities(sensors, True)


class TauronSensor(TauronAmiplusSensor):
    """Define a sensor for TAURON."""

    def __init__(self, name, user, password, meter_id, generation, sensor_type):
        """Initialize the sensor."""
        super().__init__(name, user, password, meter_id, generation, sensor_type)
