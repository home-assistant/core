"""Support for Tahoma binary sensors."""
from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import ATTR_BATTERY_LEVEL, STATE_OFF, STATE_ON

from . import DOMAIN as TAHOMA_DOMAIN, TahomaDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Tahoma controller devices."""
    if discovery_info is None:
        return
    _LOGGER.debug("Setup Tahoma Binary sensor platform")
    controller = hass.data[TAHOMA_DOMAIN]["controller"]
    devices = []
    for device in hass.data[TAHOMA_DOMAIN]["devices"]["smoke"]:
        devices.append(TahomaBinarySensor(device, controller))
    add_entities(devices, True)


class TahomaBinarySensor(TahomaDevice, BinarySensorEntity):
    """Representation of a Tahoma Binary Sensor."""

    def __init__(self, tahoma_device, controller):
        """Initialize the sensor."""
        super().__init__(tahoma_device, controller)

        self._state = None
        self._icon = None
        self._battery = None
        self._available = False

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return bool(self._state == STATE_ON)

    @property
    def device_class(self):
        """Return the class of the device."""
        if self.tahoma_device.type == "rtds:RTDSSmokeSensor":
            return "smoke"
        return None

    @property
    def icon(self):
        """Icon for device by its type."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attr = {}
        super_attr = super().device_state_attributes
        if super_attr is not None:
            attr.update(super_attr)

        if self._battery is not None:
            attr[ATTR_BATTERY_LEVEL] = self._battery
        return attr

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    def update(self):
        """Update the state."""
        self.controller.get_states([self.tahoma_device])
        if self.tahoma_device.type == "rtds:RTDSSmokeSensor":
            if self.tahoma_device.active_states["core:SmokeState"] == "notDetected":
                self._state = STATE_OFF
            else:
                self._state = STATE_ON

        if "core:SensorDefectState" in self.tahoma_device.active_states:
            # 'lowBattery' for low battery warning. 'dead' for not available.
            self._battery = self.tahoma_device.active_states["core:SensorDefectState"]
            self._available = bool(self._battery != "dead")
        else:
            self._battery = None
            self._available = True

        if self._state == STATE_ON:
            self._icon = "mdi:fire"
        elif self._battery == "lowBattery":
            self._icon = "mdi:battery-alert"
        else:
            self._icon = None

        _LOGGER.debug("Update %s, state: %s", self._name, self._state)
