"""Support for ThinkingCleaner sensors."""
from datetime import timedelta

from pythinkingcleaner import Discovery, ThinkingCleaner
import voluptuous as vol

from homeassistant import util
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_HOST, PERCENTAGE
import homeassistant.helpers.config_validation as cv

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

SENSOR_TYPES = {
    "battery": ["Battery", PERCENTAGE, "mdi:battery"],
    "state": ["State", None, None],
    "capacity": ["Capacity", None, None],
}

STATES = {
    "st_base": "On homebase: Not Charging",
    "st_base_recon": "On homebase: Reconditioning Charging",
    "st_base_full": "On homebase: Full Charging",
    "st_base_trickle": "On homebase: Trickle Charging",
    "st_base_wait": "On homebase: Waiting",
    "st_plug": "Plugged in: Not Charging",
    "st_plug_recon": "Plugged in: Reconditioning Charging",
    "st_plug_full": "Plugged in: Full Charging",
    "st_plug_trickle": "Plugged in: Trickle Charging",
    "st_plug_wait": "Plugged in: Waiting",
    "st_stopped": "Stopped",
    "st_clean": "Cleaning",
    "st_cleanstop": "Stopped with cleaning",
    "st_clean_spot": "Spot cleaning",
    "st_clean_max": "Max cleaning",
    "st_delayed": "Delayed cleaning will start soon",
    "st_dock": "Searching Homebase",
    "st_pickup": "Roomba picked up",
    "st_remote": "Remote control driving",
    "st_wait": "Waiting for command",
    "st_off": "Off",
    "st_error": "Error",
    "st_locate": "Find me!",
    "st_unknown": "Unknown state",
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Optional(CONF_HOST): cv.string})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ThinkingCleaner platform."""

    host = config.get(CONF_HOST)
    if host:
        devices = [ThinkingCleaner(host, "unknown")]
    else:
        discovery = Discovery()
        devices = discovery.discover()

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_devices():
        """Update all devices."""
        for device_object in devices:
            device_object.update()

    dev = []
    for device in devices:
        for type_name in SENSOR_TYPES:
            dev.append(ThinkingCleanerSensor(device, type_name, update_devices))

    add_entities(dev)


class ThinkingCleanerSensor(SensorEntity):
    """Representation of a ThinkingCleaner Sensor."""

    def __init__(self, tc_object, sensor_type, update_devices):
        """Initialize the ThinkingCleaner."""
        self.type = sensor_type

        self._tc_object = tc_object
        self._update_devices = update_devices
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._tc_object.name} {SENSOR_TYPES[self.type][0]}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][2]

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Update the sensor."""
        self._update_devices()

        if self.type == "battery":
            self._state = self._tc_object.battery
        elif self.type == "state":
            self._state = STATES[self._tc_object.status]
        elif self.type == "capacity":
            self._state = self._tc_object.capacity
