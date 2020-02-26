"""Support for Amcrest IP camera binary sensors."""
from datetime import timedelta
import logging

from amcrest import AmcrestError

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_MOTION,
    BinarySensorDevice,
)
from homeassistant.const import CONF_BINARY_SENSORS, CONF_NAME
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    BINARY_SENSOR_SCAN_INTERVAL_SECS,
    DATA_AMCREST,
    DEVICES,
    SERVICE_UPDATE,
)
from .helpers import log_update_error, service_signal

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=BINARY_SENSOR_SCAN_INTERVAL_SECS)

BINARY_SENSOR_MOTION_DETECTED = "motion_detected"
BINARY_SENSOR_ONLINE = "online"
# Binary sensor types are defined like: Name, device class
BINARY_SENSORS = {
    BINARY_SENSOR_MOTION_DETECTED: ("Motion Detected", DEVICE_CLASS_MOTION),
    BINARY_SENSOR_ONLINE: ("Online", DEVICE_CLASS_CONNECTIVITY),
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a binary sensor for an Amcrest IP Camera."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST][DEVICES][name]
    async_add_entities(
        [
            AmcrestBinarySensor(name, device, sensor_type)
            for sensor_type in discovery_info[CONF_BINARY_SENSORS]
        ],
        True,
    )


class AmcrestBinarySensor(BinarySensorDevice):
    """Binary sensor for Amcrest camera."""

    def __init__(self, name, device, sensor_type):
        """Initialize entity."""
        self._name = "{} {}".format(name, BINARY_SENSORS[sensor_type][0])
        self._signal_name = name
        self._api = device.api
        self._sensor_type = sensor_type
        self._state = None
        self._device_class = BINARY_SENSORS[sensor_type][1]
        self._unsub_dispatcher = None

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return self._sensor_type != BINARY_SENSOR_ONLINE

    @property
    def name(self):
        """Return entity name."""
        return self._name

    @property
    def is_on(self):
        """Return if entity is on."""
        return self._state

    @property
    def device_class(self):
        """Return device class."""
        return self._device_class

    @property
    def available(self):
        """Return True if entity is available."""
        return self._sensor_type == BINARY_SENSOR_ONLINE or self._api.available

    def update(self):
        """Update entity."""
        if not self.available:
            return
        _LOGGER.debug("Updating %s binary sensor", self._name)

        try:
            if self._sensor_type == BINARY_SENSOR_MOTION_DETECTED:
                self._state = self._api.is_motion_detected

            elif self._sensor_type == BINARY_SENSOR_ONLINE:
                self._state = self._api.available
        except AmcrestError as error:
            log_update_error(_LOGGER, "update", self.name, "binary sensor", error)

    async def async_on_demand_update(self):
        """Update state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Subscribe to update signal."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            service_signal(SERVICE_UPDATE, self._signal_name),
            self.async_on_demand_update,
        )

    async def async_will_remove_from_hass(self):
        """Disconnect from update signal."""
        self._unsub_dispatcher()
