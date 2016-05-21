"""
Support for Envisalink sensors (shows panel info).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.envisalink/
"""
import logging

from homeassistant.components.envisalink import (EVL_CONTROLLER, EnvisalinkDevice, SIGNAL_KEYPAD_UPDATE)
from homeassistant.util import convert

DEPENDENCIES = ['envisalink']
_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Perform the setup for Envisalink sensor devices."""
    _configuredPartitions = discovery_info['partitions']
    add_devices_callback(
            EnvisalinkSensor(convert(_configuredPartitions[partNum]['name'],
                                     str, str.format("Partition #{0}", partNum)),
                                     EVL_CONTROLLER.alarm_state['partition'][partNum], EVL_CONTROLLER)
        for partNum in _configuredPartitions)

class EnvisalinkSensor(EnvisalinkDevice):
    """Representation of an envisalink keypad."""
    
    def __init__(self, partitionName, info, controller):
        """Initialize the sensor."""
        from pydispatch import dispatcher
        self._icon = 'mdi:alarm'
        _LOGGER.info('Setting up sensor for partition: ' + partitionName)
        EnvisalinkDevice.__init__(self, partitionName + ' Keypad', info, controller)
        dispatcher.connect(self._update_callback, signal=SIGNAL_KEYPAD_UPDATE, sender=dispatcher.Any)

    @property
    def icon(self):
        """Return the icon if any."""
        return self._icon

    @property
    def state(self):
        return self._info['status']['alpha']    

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._info['status'] 

    def _update_callback(self):
        self.update_ha_state()
