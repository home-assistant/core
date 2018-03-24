"""
Reads vehicle status from BMW connected drive portal.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.bmw_connected_drive/
"""
import asyncio
import logging

from homeassistant.components.bmw_connected_drive import DOMAIN as BMW_DOMAIN
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['bmw_connected_drive']

_LOGGER = logging.getLogger(__name__)

LENGTH_ATTRIBUTES = {
    'remaining_range_fuel': ['Range (fuel)', 'mdi:ruler'],
    'mileage': ['Mileage', 'mdi:speedometer']
}

VALID_ATTRIBUTES = {
    'remaining_fuel': ['Remaining Fuel', 'mdi:gas-station']
}

VALID_ATTRIBUTES.update(LENGTH_ATTRIBUTES)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the BMW sensors."""
    accounts = hass.data[BMW_DOMAIN]
    _LOGGER.debug('Found BMW accounts: %s',
                  ', '.join([a.name for a in accounts]))
    devices = []
    for account in accounts:
        for vehicle in account.account.vehicles:
            for key, value in sorted(VALID_ATTRIBUTES.items()):
                device = BMWConnectedDriveSensor(account, vehicle, key,
                                                 value[0], value[1])
                devices.append(device)
    add_devices(devices, True)


class BMWConnectedDriveSensor(Entity):
    """Representation of a BMW vehicle sensor."""

    def __init__(self, account, vehicle, attribute: str, sensor_name, icon):
        """Constructor."""
        self._vehicle = vehicle
        self._account = account
        self._attribute = attribute
        self._state = None
        self._unit_of_measurement = None
        self._name = '{} {}'.format(self._vehicle.name, self._attribute)
        self._sensor_name = sensor_name
        self._icon = icon

    @property
    def should_poll(self) -> bool:
        """Data update is triggered from BMWConnectedDriveEntity."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor.

        The return type of this call depends on the attribute that
        is configured.
        """
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Get the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the binary sensor."""
        return {
            'car': self._vehicle.name
        }

    def update(self) -> None:
        """Read new state data from the library."""
        _LOGGER.debug('Updating %s', self._vehicle.name)
        vehicle_state = self._vehicle.state
        self._state = getattr(vehicle_state, self._attribute)

        if self._attribute in LENGTH_ATTRIBUTES:
            self._unit_of_measurement = 'km'
        elif self._attribute == 'remaining_fuel':
            self._unit_of_measurement = 'l'
        else:
            self._unit_of_measurement = None

    def update_callback(self):
        """Schedule a state update."""
        self.schedule_update_ha_state(True)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add callback after being added to hass.

        Show latest data after startup.
        """
        self._account.add_update_listener(self.update_callback)
