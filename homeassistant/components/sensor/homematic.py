import logging

"""
The homematic sensor platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.homematic/
"""

from homeassistant.helpers.entity import Entity
import homeassistant.components.homematic as homematic

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyhomematic==0.1.2']

# List of component names (string) your component depends upon.
DEPENDENCIES = ['homematic']

SENSOR_TYPES = {
    "HMWindowHandle": "handle",
}

def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    return homematic.setup_hmdevice_entity_helper(HMSensor, config, add_callback_devices)


class HMSensor(homematic.HMDevice, Entity):
    """Represents diverse Homematic sensors in Home Assistant."""
    def __init__(self, config):
        super().__init__(config)
        self._sabotage = None
        self._sensor_class = None
        self._battery_low = None
    
    @property
    def state(self):
        """Return the state of the sensor."""
        if self.sensor_class == "handle":
            """ (0=closed, 1=tilted, 2=open) """
            HANDLE_STATE = {0 : "closed", 1 : "tilted", 2 : "open"} 
            return HANDLE_STATE.get(self._state, None) 
        
        return self._state

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return self._sensor_class

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        attr = {}

        if self.sensor_class is not None:
            attr['Sensor Class'] = self.sensor_class
            if self.sensor_class == 'handle':
                if self._battery_low:
                    attr['Battery'] = 'low'
                if self._sabotage:
                    attr['Sabotage'] = True
        return attr

    def connect_to_homematic(self):
        """Configuration specific to device after connection with pyhomematic is established"""
        def event_received(device, caller, attribute, value):
            attribute = str(attribute).upper()
            if attribute == 'STATE':
                self._state = value
            elif attribute == 'LOWBAT':
                self._battery_low = True
            elif attribute == 'ERROR' and value == 1:
                self._sabotage = True
            elif attribute == 'UNREACH':
                self._is_available = not bool(value)
            else:
                return
            self.update_ha_state()

        super().connect_to_homematic()

        self._sensor_class = SENSOR_TYPES.get(type(self._hmdevice).__name__, None) 
        if self._is_available:
            self._state = self._hmdevice.state
            self._sabotage = self._hmdevice.sabotage
            self._battery_low = self._hmdevice.low_batt
            self._hmdevice.setEventCallback(event_received)
            self.update_ha_state()
