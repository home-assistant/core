"""
Reads vehicle status from BMW connected drive portal.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.bmw_connected_drive/
"""
import logging
import asyncio

from homeassistant.components.bmw_connected_drive import DOMAIN as BMW_DOMAIN
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['bmw_connected_drive']

_LOGGER = logging.getLogger(__name__)

LENGTH_ATTRIBUTES = [
    'remaining_range_fuel',
    'mileage',
    ]

VALID_ATTRIBUTES = LENGTH_ATTRIBUTES + [
    'remaining_fuel',
]


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the BMW sensors."""
    accounts = hass.data[BMW_DOMAIN]
    _LOGGER.debug('Found BMW accounts: %s',
                  ', '.join([a.name for a in accounts]))
    devices = []
    for account in accounts:
        for vehicle in account.account.vehicles:
            for sensor in VALID_ATTRIBUTES:
                device = BMWConnectedDriveSensor(account, vehicle, sensor)
                devices.append(device)
    add_devices(devices)


class BMWConnectedDriveSensor(Entity):
    """Representation of a BMW vehicle sensor."""

    def __init__(self, account, vehicle, attribute: str):
        """Constructor."""
        self._vehicle = vehicle
        self._account = account
        self._attribute = attribute
        self._state = None
        self._unit_of_measurement = None
        self._name = '{} {}'.format(self._vehicle.modelName, self._attribute)

    @property
    def should_poll(self) -> bool:
        """Data update is triggered from BMWConnectedDriveEntity."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

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

    def update(self) -> None:
        """Read new state data from the library."""
        _LOGGER.debug('Updating %s', self.entity_id)
        vehicle_state = self._vehicle.state
        self._state = getattr(vehicle_state, self._attribute)

        if self._attribute in LENGTH_ATTRIBUTES:
            self._unit_of_measurement = vehicle_state.unit_of_length
        elif self._attribute == 'remaining_fuel':
            self._unit_of_measurement = vehicle_state.unit_of_volume
        else:
            self._unit_of_measurement = None

        self.schedule_update_ha_state()

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add callback after being added to hass.

        Show latest data after startup.
        """
        self._account.add_update_listener(self.update)
        yield from self.hass.async_add_job(self.update)
