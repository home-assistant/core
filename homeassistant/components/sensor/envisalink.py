"""
Support for Envisalink sensors (shows panel info).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.envisalink/
"""
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.envisalink import (EVL_CONTROLLER,
                                                 PARTITION_SCHEMA,
                                                 CONF_PARTITIONNAME,
                                                 EnvisalinkDevice,
                                                 SIGNAL_KEYPAD_UPDATE)
from homeassistant.util import convert

DEPENDENCIES = ['envisalink']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Perform the setup for Envisalink sensor devices."""
    _configured_partitions = discovery_info['partitions']
    for partNum in _configured_partitions:
        try:
            _LOGGER.info(str.format("Validating config for partition: {0}", partNum))
            _device_config_data = PARTITION_SCHEMA(_configured_partitions[partNum])
            _device = EnvisalinkSensor(
                      _device_config_data[CONF_PARTITIONNAME],
                      partNum,
                      EVL_CONTROLLER.alarm_state['partition'][partNum],
                      EVL_CONTROLLER)
            add_devices_callback([_device])
        except vol.MultipleInvalid:
            _LOGGER.error('Failed to load partition. A partition name is required.')


class EnvisalinkSensor(EnvisalinkDevice):
    """Representation of an envisalink keypad."""

    def __init__(self, partition_name, partition_number, info, controller):
        """Initialize the sensor."""
        from pydispatch import dispatcher
        self._icon = 'mdi:alarm'
        self._partition_number = partition_number
        _LOGGER.info('Setting up sensor for partition: ' + partition_name)
        EnvisalinkDevice.__init__(self,
                                  partition_name + ' Keypad',
                                  info,
                                  controller)

        dispatcher.connect(self._update_callback,
                           signal=SIGNAL_KEYPAD_UPDATE,
                           sender=dispatcher.Any)

    @property
    def icon(self):
        """Return the icon if any."""
        return self._icon

    @property
    def state(self):
        """Return the overall state."""
        return self._info['status']['alpha']

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._info['status']

    def _update_callback(self, partition):
        """Update the partition state in HA, if needed."""
        if partition is None or int(partition) == self._partition_number:
            self.update_ha_state()
