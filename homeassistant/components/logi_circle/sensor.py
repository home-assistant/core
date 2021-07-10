"""Support for Logi Circle sensors."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_BATTERY_CHARGING,
    CONF_MONITORED_CONDITIONS,
    CONF_SENSORS,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.util.dt import as_local

from .const import (
    ATTRIBUTION,
    DEVICE_BRAND,
    DOMAIN as LOGI_CIRCLE_DOMAIN,
    LOGI_SENSORS as SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a sensor for a Logi Circle device. Obsolete."""
    _LOGGER.warning("Logi Circle no longer works with sensor platform configuration")


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Logi Circle sensor based on a config entry."""
    devices = await hass.data[LOGI_CIRCLE_DOMAIN].cameras
    time_zone = str(hass.config.time_zone)

    sensors = []
    for sensor_type in entry.data.get(CONF_SENSORS).get(CONF_MONITORED_CONDITIONS):
        for device in devices:
            if device.supports_feature(sensor_type):
                sensors.append(LogiSensor(device, time_zone, sensor_type))

    async_add_entities(sensors, True)


class LogiSensor(SensorEntity):
    """A sensor implementation for a Logi Circle camera."""

    def __init__(self, camera, time_zone, sensor_type):
        """Initialize a sensor for Logi Circle camera."""
        self._sensor_type = sensor_type
        self._camera = camera
        self._id = f"{self._camera.mac_address}-{self._sensor_type}"
        self._icon = f"mdi:{SENSOR_TYPES.get(self._sensor_type)[2]}"
        self._name = f"{self._camera.name} {SENSOR_TYPES.get(self._sensor_type)[0]}"
        self._activity = {}
        self._state = None
        self._tz = time_zone

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "name": self._camera.name,
            "identifiers": {(LOGI_CIRCLE_DOMAIN, self._camera.id)},
            "model": self._camera.model_name,
            "sw_version": self._camera.firmware,
            "manufacturer": DEVICE_BRAND,
        }

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        state = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "battery_saving_mode": (
                STATE_ON if self._camera.battery_saving else STATE_OFF
            ),
            "microphone_gain": self._camera.microphone_gain,
        }

        if self._sensor_type == "battery_level":
            state[ATTR_BATTERY_CHARGING] = self._camera.charging

        return state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._sensor_type == "battery_level" and self._state is not None:
            return icon_for_battery_level(
                battery_level=int(self._state), charging=False
            )
        if self._sensor_type == "recording_mode" and self._state is not None:
            return "mdi:eye" if self._state == STATE_ON else "mdi:eye-off"
        if self._sensor_type == "streaming_mode" and self._state is not None:
            return "mdi:camera" if self._state == STATE_ON else "mdi:camera-off"
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES.get(self._sensor_type)[1]

    async def async_update(self):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Pulling data from %s sensor", self._name)
        await self._camera.update()

        if self._sensor_type == "last_activity_time":
            last_activity = await self._camera.get_last_activity(force_refresh=True)
            if last_activity is not None:
                last_activity_time = as_local(last_activity.end_time_utc)
                self._state = (
                    f"{last_activity_time.hour:0>2}:{last_activity_time.minute:0>2}"
                )
        else:
            state = getattr(self._camera, self._sensor_type, None)
            if isinstance(state, bool):
                self._state = STATE_ON if state is True else STATE_OFF
            else:
                self._state = state
            self._state = state
