"""Support for Envisalink sensors (shows panel info)."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    ATTR_PARTITION,
    DATA_EVL,
    PARTITION_SCHEMA,
    SIGNAL_KEYPAD_UPDATE,
    SIGNAL_PARTITION_UPDATE,
    USERS_SCHEMA,
    EnvisalinkDevice,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Perform the setup for Envisalink sensor devices."""
    configured_partitions = discovery_info["partitions"]
    configured_users = discovery_info["users"]

    user_list = {}
    if configured_users:
        for user_num in configured_users:
            user_list[user_num] = USERS_SCHEMA(configured_users[user_num])[CONF_NAME]

    devices = []
    for part_num in configured_partitions:
        device_config_data = PARTITION_SCHEMA(configured_partitions[part_num])
        device = EnvisalinkSensor(
            hass,
            device_config_data[CONF_NAME],
            part_num,
            hass.data[DATA_EVL].alarm_state["partition"][part_num],
            user_list,
            hass.data[DATA_EVL],
        )

        devices.append(device)

    async_add_entities(devices)


class EnvisalinkSensor(EnvisalinkDevice, SensorEntity):
    """Representation of an Envisalink keypad."""

    def __init__(self, hass, partition_name, partition_number, info, users, controller):
        """Initialize the sensor."""
        self._icon = "mdi:security"
        self._partition_number = partition_number
        self._users = users

        _LOGGER.debug("Setting up sensor for partition: %s", partition_name)
        super().__init__(f"{partition_name} Keypad", info, controller)

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(self.hass, SIGNAL_KEYPAD_UPDATE, self._update_callback)
        async_dispatcher_connect(
            self.hass, SIGNAL_PARTITION_UPDATE, self._update_callback
        )

    @property
    def icon(self):
        """Return the icon if any."""
        return self._icon

    @property
    def native_value(self):
        """Return the overall state."""
        return self._info["status"]["alpha"]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr[ATTR_PARTITION] = self._partition_number
        attr.update(self._info["status"])
        last_armed_by_user = attr["last_armed_by_user"]
        last_disarmed_by_user = attr["last_disarmed_by_user"]
        if last_armed_by_user in self._users:
            attr["last_armed_by_user"] = self._users[last_armed_by_user]
        if last_disarmed_by_user in self._users:
            attr["last_disarmed_by_user"] = self._users[last_disarmed_by_user]
        return attr

    @callback
    def _update_callback(self, partition):
        """Update the partition state in HA, if needed."""
        if partition is None or int(partition) == self._partition_number:
            self.async_write_ha_state()
