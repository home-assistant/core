"""Support for Android IP Webcam sensors."""
from homeassistant.helpers.icon import icon_for_battery_level

from . import (
    CONF_HOST,
    CONF_NAME,
    CONF_SENSORS,
    DATA_IP_WEBCAM,
    ICON_MAP,
    KEY_MAP,
    AndroidIPCamEntity,
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the IP Webcam Sensor."""
    if discovery_info is None:
        return

    host = discovery_info[CONF_HOST]
    name = discovery_info[CONF_NAME]
    sensors = discovery_info[CONF_SENSORS]
    ipcam = hass.data[DATA_IP_WEBCAM][host]

    all_sensors = []

    for sensor in sensors:
        all_sensors.append(IPWebcamSensor(name, host, ipcam, sensor))

    async_add_entities(all_sensors, True)


class IPWebcamSensor(AndroidIPCamEntity):
    """Representation of a IP Webcam sensor."""

    def __init__(self, name, host, ipcam, sensor):
        """Initialize the sensor."""
        super().__init__(host, ipcam)

        self._sensor = sensor
        self._mapped_name = KEY_MAP.get(self._sensor, self._sensor)
        self._name = f"{name} {self._mapped_name}"
        self._state = None
        self._unit = None

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Retrieve latest state."""
        if self._sensor in ("audio_connections", "video_connections"):
            if not self._ipcam.status_data:
                return
            self._state = self._ipcam.status_data.get(self._sensor)
            self._unit = "Connections"
        else:
            self._state, self._unit = self._ipcam.export_sensor(self._sensor)

    @property
    def icon(self):
        """Return the icon for the sensor."""
        if self._sensor == "battery_level" and self._state is not None:
            return icon_for_battery_level(int(self._state))
        return ICON_MAP.get(self._sensor, "mdi:eye")
