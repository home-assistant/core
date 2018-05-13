"""
Reads vehicle status from BMW connected drive portal.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.bmw_connected_drive/
"""
import asyncio
import logging

from homeassistant.components.bmw_connected_drive import DOMAIN as BMW_DOMAIN
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

DEPENDENCIES = ['bmw_connected_drive']

_LOGGER = logging.getLogger(__name__)

ATTR_TO_HA = {
    'mileage': ['mdi:speedometer', 'km'],
    'remaining_range_total': ['mdi:ruler', 'km'],
    'remaining_range_electric': ['mdi:ruler', 'km'],
    'remaining_range_fuel': ['mdi:ruler', 'km'],
    'max_range_electric': ['mdi:ruler', 'km'],
    'remaining_fuel': ['mdi:gas-station', 'l'],
    'charging_time_remaining': ['mdi:update', 'h'],
    'charging_status': ['mdi:battery-charging', None]
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the BMW sensors."""
    accounts = hass.data[BMW_DOMAIN]
    _LOGGER.debug('Found BMW accounts: %s',
                  ', '.join([a.name for a in accounts]))
    devices = []
    for account in accounts:
        for vehicle in account.account.vehicles:
            for attribute_name in vehicle.drive_train_attributes:
                device = BMWConnectedDriveSensor(account, vehicle,
                                                 attribute_name)
                devices.append(device)
            device = BMWConnectedDriveSensor(account, vehicle, 'mileage')
            devices.append(device)
    add_devices(devices, True)


class BMWConnectedDriveSensor(Entity):
    """Representation of a BMW vehicle sensor."""

    def __init__(self, account, vehicle, attribute: str):
        """Constructor."""
        self._vehicle = vehicle
        self._account = account
        self._attribute = attribute
        self._state = None
        self._name = '{} {}'.format(self._vehicle.name, self._attribute)
        self._unique_id = '{}-{}'.format(self._vehicle.vin, self._attribute)

    @property
    def should_poll(self) -> bool:
        """Data update is triggered from BMWConnectedDriveEntity."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        from bimmer_connected.state import ChargingState
        vehicle_state = self._vehicle.state
        charging_state = vehicle_state.charging_status in \
            [ChargingState.CHARGING]

        if self._attribute == 'charging_level_hv':
            return icon_for_battery_level(
                battery_level=vehicle_state.charging_level_hv,
                charging=charging_state)
        icon, _ = ATTR_TO_HA.get(self._attribute, [None, None])
        return icon

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
        _, unit = ATTR_TO_HA.get(self._attribute, [None, None])
        return unit

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            'car': self._vehicle.name
        }

    def update(self) -> None:
        """Read new state data from the library."""
        _LOGGER.debug('Updating %s', self._vehicle.name)
        vehicle_state = self._vehicle.state
        if self._attribute == 'charging_status':
            self._state = getattr(vehicle_state, self._attribute).value
        else:
            self._state = getattr(vehicle_state, self._attribute)

    def update_callback(self):
        """Schedule a state update."""
        self.schedule_update_ha_state(True)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add callback after being added to hass.

        Show latest data after startup.
        """
        self._account.add_update_listener(self.update_callback)
