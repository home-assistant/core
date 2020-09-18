"""Support for Tahoma sensors."""
from datetime import timedelta
import logging

from homeassistant.const import ATTR_BATTERY_LEVEL, PERCENTAGE, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

from . import DOMAIN as TAHOMA_DOMAIN, TahomaDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

ATTR_RSSI_LEVEL = "rssi_level"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Tahoma controller devices."""
    if discovery_info is None:
        return
    controller = hass.data[TAHOMA_DOMAIN]["controller"]
    devices = []
    for device in hass.data[TAHOMA_DOMAIN]["devices"]["sensor"]:
        devices.append(TahomaSensor(device, controller))
    add_entities(devices, True)


class TahomaSensor(TahomaDevice, Entity):
    """Representation of a Tahoma Sensor."""

    def __init__(self, tahoma_device, controller):
        """Initialize the sensor."""
        self.current_value = None
        self._available = False
        super().__init__(tahoma_device, controller)

    @property
    def state(self):
        """Return the name of the sensor."""
        return self.current_value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self.tahoma_device.type == "io:TemperatureIOSystemSensor":
            return TEMP_CELSIUS
        if self.tahoma_device.type == "io:SomfyContactIOSystemSensor":
            return None
        if self.tahoma_device.type == "io:SomfyBasicContactIOSystemSensor":
            return None
        if self.tahoma_device.type == "io:LightIOSystemSensor":
            return "lx"
        if self.tahoma_device.type == "Humidity Sensor":
            return PERCENTAGE
        if self.tahoma_device.type == "rtds:RTDSContactSensor":
            return None
        if self.tahoma_device.type == "rtds:RTDSMotionSensor":
            return None
        if (
            self.tahoma_device.type
            == "somfythermostat:SomfyThermostatTemperatureSensor"
        ):
            return TEMP_CELSIUS
        if self.tahoma_device.type == "somfythermostat:SomfyThermostatHumiditySensor":
            return PERCENTAGE

    def update(self):
        """Update the state."""
        self.controller.get_states([self.tahoma_device])
        if self.tahoma_device.type == "io:LightIOSystemSensor":
            self.current_value = self.tahoma_device.active_states["core:LuminanceState"]
            self._available = bool(
                self.tahoma_device.active_states.get("core:StatusState") == "available"
            )
        if self.tahoma_device.type == "io:SomfyContactIOSystemSensor":
            self.current_value = self.tahoma_device.active_states["core:ContactState"]
            self._available = bool(
                self.tahoma_device.active_states.get("core:StatusState") == "available"
            )
        if self.tahoma_device.type == "io:SomfyBasicContactIOSystemSensor":
            self.current_value = self.tahoma_device.active_states["core:ContactState"]
            self._available = bool(
                self.tahoma_device.active_states.get("core:StatusState") == "available"
            )
        if self.tahoma_device.type == "rtds:RTDSContactSensor":
            self.current_value = self.tahoma_device.active_states["core:ContactState"]
            self._available = True
        if self.tahoma_device.type == "rtds:RTDSMotionSensor":
            self.current_value = self.tahoma_device.active_states["core:OccupancyState"]
            self._available = True
        if self.tahoma_device.type == "io:TemperatureIOSystemSensor":
            self.current_value = round(
                float(self.tahoma_device.active_states["core:TemperatureState"]), 1
            )
            self._available = True
        if (
            self.tahoma_device.type
            == "somfythermostat:SomfyThermostatTemperatureSensor"
        ):
            self.current_value = float(
                f"{self.tahoma_device.active_states['core:TemperatureState']:.2f}"
            )
            self._available = True
        if self.tahoma_device.type == "somfythermostat:SomfyThermostatHumiditySensor":
            self.current_value = float(
                f"{self.tahoma_device.active_states['core:RelativeHumidityState']:.2f}"
            )
            self._available = True

        _LOGGER.debug("Update %s, value: %d", self._name, self.current_value)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attr = {}
        super_attr = super().device_state_attributes
        if super_attr is not None:
            attr.update(super_attr)

        if "core:RSSILevelState" in self.tahoma_device.active_states:
            attr[ATTR_RSSI_LEVEL] = self.tahoma_device.active_states[
                "core:RSSILevelState"
            ]
        if "core:SensorDefectState" in self.tahoma_device.active_states:
            attr[ATTR_BATTERY_LEVEL] = self.tahoma_device.active_states[
                "core:SensorDefectState"
            ]
        return attr

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available
