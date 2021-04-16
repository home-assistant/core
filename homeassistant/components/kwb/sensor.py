"""Support for KWB Easyfire."""
from pykwb import kwb
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv

DEFAULT_RAW = False
DEFAULT_NAME = "KWB"

MODE_SERIAL = 0
MODE_TCP = 1

CONF_TYPE = "type"
CONF_RAW = "raw"

SERIAL_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_RAW, default=DEFAULT_RAW): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_DEVICE): cv.string,
        vol.Required(CONF_TYPE): "serial",
    }
)

ETHERNET_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_RAW, default=DEFAULT_RAW): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_TYPE): "tcp",
    }
)

PLATFORM_SCHEMA = vol.Schema(vol.Any(SERIAL_SCHEMA, ETHERNET_SCHEMA))


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the KWB component."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    device = config.get(CONF_DEVICE)
    connection_type = config.get(CONF_TYPE)
    raw = config.get(CONF_RAW)
    client_name = config.get(CONF_NAME)

    if connection_type == "serial":
        easyfire = kwb.KWBEasyfire(MODE_SERIAL, "", 0, device)
    elif connection_type == "tcp":
        easyfire = kwb.KWBEasyfire(MODE_TCP, host, port)
    else:
        return False

    easyfire.run_thread()

    sensors = []
    for sensor in easyfire.get_sensors():
        if (sensor.sensor_type != kwb.PROP_SENSOR_RAW) or (
            sensor.sensor_type == kwb.PROP_SENSOR_RAW and raw
        ):
            sensors.append(KWBSensor(easyfire, sensor, client_name))

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, lambda event: easyfire.stop_thread())

    add_entities(sensors)


class KWBSensor(SensorEntity):
    """Representation of a KWB Easyfire sensor."""

    def __init__(self, easyfire, sensor, client_name):
        """Initialize the KWB sensor."""
        self._easyfire = easyfire
        self._sensor = sensor
        self._client_name = client_name
        self._name = self._sensor.name

    @property
    def name(self):
        """Return the name."""
        return f"{self._client_name} {self._name}"

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self._sensor.available

    @property
    def state(self):
        """Return the state of value."""
        if self._sensor.value is not None and self._sensor.available:
            return self._sensor.value
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._sensor.unit_of_measurement
