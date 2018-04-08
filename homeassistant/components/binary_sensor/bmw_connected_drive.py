"""
Reads vehicle status from BMW connected drive portal.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.bmw_connected_drive/
"""
import asyncio
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.bmw_connected_drive import DOMAIN as BMW_DOMAIN

DEPENDENCIES = ['bmw_connected_drive']

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    'lids': ['Doors', 'opening'],
    'windows': ['Windows', 'opening'],
    'door_lock_state': ['Door lock state', 'safety']
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the BMW sensors."""
    accounts = hass.data[BMW_DOMAIN]
    _LOGGER.debug('Found BMW accounts: %s',
                  ', '.join([a.name for a in accounts]))
    devices = []
    for account in accounts:
        for vehicle in account.account.vehicles:
            for key, value in sorted(SENSOR_TYPES.items()):
                device = BMWConnectedDriveSensor(account, vehicle, key,
                                                 value[0], value[1])
                devices.append(device)
    add_devices(devices, True)


class BMWConnectedDriveSensor(BinarySensorDevice):
    """Representation of a BMW vehicle binary sensor."""

    def __init__(self, account, vehicle, attribute: str, sensor_name,
                 device_class):
        """Constructor."""
        self._account = account
        self._vehicle = vehicle
        self._attribute = attribute
        self._name = '{} {}'.format(self._vehicle.name, self._attribute)
        self._sensor_name = sensor_name
        self._device_class = device_class
        self._state = None

    @property
    def should_poll(self) -> bool:
        """Data update is triggered from BMWConnectedDriveEntity."""
        return False

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._device_class

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the binary sensor."""
        vehicle_state = self._vehicle.state
        result = {
            'car': self._vehicle.name
        }

        if self._attribute == 'lids':
            for lid in vehicle_state.lids:
                result[lid.name] = lid.state.value
        elif self._attribute == 'windows':
            for window in vehicle_state.windows:
                result[window.name] = window.state.value
        elif self._attribute == 'door_lock_state':
            result['door_lock_state'] = vehicle_state.door_lock_state.value

        return result

    def update(self):
        """Read new state data from the library."""
        from bimmer_connected.state import LockState
        vehicle_state = self._vehicle.state

        # device class opening: On means open, Off means closed
        if self._attribute == 'lids':
            _LOGGER.debug("Status of lid: %s", vehicle_state.all_lids_closed)
            self._state = not vehicle_state.all_lids_closed
        if self._attribute == 'windows':
            self._state = not vehicle_state.all_windows_closed
        # device class safety: On means unsafe, Off means safe
        if self._attribute == 'door_lock_state':
            # Possible values: LOCKED, SECURED, SELECTIVE_LOCKED, UNLOCKED
            self._state = vehicle_state.door_lock_state not in \
                          [LockState.LOCKED, LockState.SECURED]

    def update_callback(self):
        """Schedule a state update."""
        self.schedule_update_ha_state(True)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add callback after being added to hass.

        Show latest data after startup.
        """
        self._account.add_update_listener(self.update_callback)
