"""Support for Envisalink sensors (shows panel info)."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import (
    CONF_PARTITIONNAME, DATA_EVL, PARTITION_SCHEMA, SIGNAL_KEYPAD_UPDATE,
    SIGNAL_PARTITION_UPDATE, EnvisalinkDevice)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['envisalink']


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Perform the setup for Envisalink sensor devices."""
    configured_partitions = discovery_info['partitions']

    devices = []
    for part_num in configured_partitions:
        device_config_data = PARTITION_SCHEMA(configured_partitions[part_num])
        device = EnvisalinkSensor(
            hass, device_config_data[CONF_PARTITIONNAME], part_num,
            hass.data[DATA_EVL].alarm_state['partition'][part_num],
            hass.data[DATA_EVL])

        devices.append(device)

    async_add_entities(devices)


class EnvisalinkSensor(EnvisalinkDevice, Entity):
    """Representation of an Envisalink keypad."""

    def __init__(self, hass, partition_name, partition_number, info,
                 controller):
        """Initialize the sensor."""
        self._icon = 'mdi:alarm'
        self._partition_number = partition_number

        _LOGGER.debug("Setting up sensor for partition: %s", partition_name)
        super().__init__(partition_name + ' Keypad', info, controller)

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_KEYPAD_UPDATE, self._update_callback)
        async_dispatcher_connect(
            self.hass, SIGNAL_PARTITION_UPDATE, self._update_callback)

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

    @callback
    def _update_callback(self, partition):
        """Update the partition state in HA, if needed."""
        if partition is None or int(partition) == self._partition_number:
            self.async_schedule_update_ha_state()
