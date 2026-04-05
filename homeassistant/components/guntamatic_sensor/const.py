"""Constants for the guntamatic integration."""

from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

DOMAIN = "guntamatic_sensor"
SCAN_INTERVAL = timedelta(seconds=30)
DIAGNOSTIC_SENSORS = {"Serial", "Version", "Operat. time", "Service Hrs"}


UNIT_TO_DEVICE_CLASS: dict[str, SensorDeviceClass] = {
    "°C": SensorDeviceClass.TEMPERATURE,
    "h": SensorDeviceClass.DURATION,
    "d": SensorDeviceClass.DURATION,
}

UNIT_TO_STATE_CLASS: dict[str, SensorStateClass] = {
    "°C": SensorStateClass.MEASUREMENT,
    "%": SensorStateClass.MEASUREMENT,
}
