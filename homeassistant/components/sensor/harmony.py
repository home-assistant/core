#####SENSOR####
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_PORT
import homeassistant.components.harmony as harmony
import pyharmony
import logging


DEPENDENCIES = ['harmony']
_LOGGER = logging.getLogger(__name__)
CONF_IP = 'ip'





def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    for hub in harmony.HUB_CONF_GLOBAL:
        add_devices([HarmonySensor(hub[CONF_NAME],hub[CONF_USERNAME],
                                   hub[CONF_PASSWORD],
                                   hub[CONF_IP],
                                   hub[CONF_PORT])])
    return True


class HarmonySensor(harmony.HarmonyDevice, Entity):
    """Representation of a Harmony Sensor."""
    def __init__(self, name, username, password, ip, port):
        super().__init__(name, username, password, ip, port)
        self._name = 'harmony_' + self._name


    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name


    @property
    def state(self):
        """Return the state of the sensor."""
        return self.get_status()


    def get_status(self): 
        return pyharmony.ha_get_current_activity(self._email, self._password, self._ip, self._port)

        
   





