"""Support for OpenUV sensors."""
import logging

from datetime import timedelta
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from .const import (
    CONF_METER_ID,
    TYPE_ZONE,
    TYPE_CONSUMPTION_DAILY,
    TYPE_CONSUMPTION_MONTHLY,
    TYPE_CONSUMPTION_YEARLY,
)
from . import TauronAmiplusSensor

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    # TYPE_ZONE: ("Strefa", "mdi:counter", timedelta(minutes=1), None),
    TYPE_CONSUMPTION_DAILY: ("Dzienne zużycie energii", timedelta(hours=1), "kWh"),
    TYPE_CONSUMPTION_MONTHLY: ("Miesięczne zużycie energii", timedelta(hours=1), "kWh"),
    TYPE_CONSUMPTION_YEARLY: ("Roczne zużycie energii", timedelta(hours=1), "kWh"),
}


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
        name, interval, unit = SENSOR_TYPES[sensor_type]
        sensors.append(
            TauronSensor(name, user, password, meter_id, sensor_type, unit, interval)
        )

    async_add_entities(sensors, True)


class TauronSensor(TauronAmiplusSensor):
    """Define a sensor for TAURON."""

    def __init__(self, name, user, password, meter_id, sensor_type, unit, interval):
        """Initialize the sensor."""
        super().__init__(name, user, password, meter_id, sensor_type, unit, interval)
