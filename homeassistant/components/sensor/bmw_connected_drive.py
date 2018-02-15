"""
Reads vehicle status from BMW connected drive portal.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.bmw_connected_drive/
"""
import logging

from homeassistant.components.bmw_connected_drive import DOMAIN as BMW_DOMAIN
from homeassistant.helpers.entity import Entity


_LOGGER = logging.getLogger(__name__)

LENGTH_ATTRIBUTES = [
    'remaining_range_fuel',
    'mileage',
    ]

VAILD_ATTRIBUTES = LENGTH_ATTRIBUTES + [
    'remaining_fuel',
]


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the BMW sensors."""
    entities = hass.data[BMW_DOMAIN]
    _LOGGER.debug('Found BMW accounts: %s',
                  ', '.join([v.name for v in entities]))
    devices = []
    for entity in entities:
        account = entity.account
        for vehicle in account.vehicles:
            for sensor in VAILD_ATTRIBUTES:
                device = BMWConnectedDriveSensor(entity, account,
                                                 vehicle, sensor)
                devices.append(device)
    return add_devices(devices)


class BMWConnectedDriveSensor(Entity):
    """Representation of a BMW vehicle."""

    def __init__(self, entity, account, vehicle, attribute: str):
        """Constructor."""
        self._vehicle = vehicle
        self._attribute = attribute
        self._state = None
        self._unit_of_measurement = None
        self._name = '{} {}'.format(self._vehicle.modelName, self._attribute)
        entity.add_update_listener(self.update)

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
        vehicle_state = self._vehicle.state
        self._state = getattr(vehicle_state, self._attribute)

        if self._attribute in LENGTH_ATTRIBUTES:
            self._unit_of_measurement = vehicle_state.unit_of_length
        elif self._attribute == 'remaining_fuel':
            self._unit_of_measurement = vehicle_state.unit_of_volume
        else:
            self._unit_of_measurement = None

        self.schedule_update_ha_state()
