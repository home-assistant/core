"""Support for BMW car locks with BMW ConnectedDrive."""
import logging

from homeassistant.components.lock import LockDevice
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED

from . import DOMAIN as BMW_DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the BMW Connected Drive lock."""
    accounts = hass.data[BMW_DOMAIN]
    _LOGGER.debug('Found BMW accounts: %s',
                  ', '.join([a.name for a in accounts]))
    devices = []
    for account in accounts:
        if not account.read_only:
            for vehicle in account.account.vehicles:
                device = BMWLock(account, vehicle, 'lock', 'BMW lock')
                devices.append(device)
    add_entities(devices, True)


class BMWLock(LockDevice):
    """Representation of a BMW vehicle lock."""

    def __init__(self, account, vehicle, attribute: str, sensor_name):
        """Initialize the lock."""
        self._account = account
        self._vehicle = vehicle
        self._attribute = attribute
        self._name = '{} {}'.format(self._vehicle.name, self._attribute)
        self._unique_id = '{}-{}'.format(self._vehicle.vin, self._attribute)
        self._sensor_name = sensor_name
        self._state = None

    @property
    def should_poll(self):
        """Do not poll this class.

        Updates are triggered from BMWConnectedDriveAccount.
        """
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the lock."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the lock."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the lock."""
        vehicle_state = self._vehicle.state
        return {
            'car': self._vehicle.name,
            'door_lock_state': vehicle_state.door_lock_state.value
        }

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._state == STATE_LOCKED

    def lock(self, **kwargs):
        """Lock the car."""
        _LOGGER.debug("%s: locking doors", self._vehicle.name)
        # Optimistic state set here because it takes some time before the
        # update callback response
        self._state = STATE_LOCKED
        self.schedule_update_ha_state()
        self._vehicle.remote_services.trigger_remote_door_lock()

    def unlock(self, **kwargs):
        """Unlock the car."""
        _LOGGER.debug("%s: unlocking doors", self._vehicle.name)
        # Optimistic state set here because it takes some time before the
        # update callback response
        self._state = STATE_UNLOCKED
        self.schedule_update_ha_state()
        self._vehicle.remote_services.trigger_remote_door_unlock()

    def update(self):
        """Update state of the lock."""
        from bimmer_connected.state import LockState

        _LOGGER.debug("%s: updating data for %s", self._vehicle.name,
                      self._attribute)
        vehicle_state = self._vehicle.state

        # Possible values: LOCKED, SECURED, SELECTIVE_LOCKED, UNLOCKED
        self._state = STATE_LOCKED \
            if vehicle_state.door_lock_state \
            in [LockState.LOCKED, LockState.SECURED] \
            else STATE_UNLOCKED

    def update_callback(self):
        """Schedule a state update."""
        self.schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Add callback after being added to hass.

        Show latest data after startup.
        """
        self._account.add_update_listener(self.update_callback)
