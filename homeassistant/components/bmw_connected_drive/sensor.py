"""Support for reading vehicle status from BMW connected drive portal."""
import logging

from homeassistant.const import (
    CONF_UNIT_SYSTEM_IMPERIAL, LENGTH_KILOMETERS, LENGTH_MILES, VOLUME_GALLONS,
    VOLUME_LITERS)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

from . import DOMAIN as BMW_DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_TO_HA_METRIC = {
    'mileage': ['mdi:speedometer', LENGTH_KILOMETERS],
    'remaining_range_total': ['mdi:ruler', LENGTH_KILOMETERS],
    'remaining_range_electric': ['mdi:ruler', LENGTH_KILOMETERS],
    'remaining_range_fuel': ['mdi:ruler', LENGTH_KILOMETERS],
    'max_range_electric': ['mdi:ruler', LENGTH_KILOMETERS],
    'remaining_fuel': ['mdi:gas-station', VOLUME_LITERS],
    'charging_time_remaining': ['mdi:update', 'h'],
    'charging_status': ['mdi:battery-charging', None],
}

ATTR_TO_HA_IMPERIAL = {
    'mileage': ['mdi:speedometer', LENGTH_MILES],
    'remaining_range_total': ['mdi:ruler', LENGTH_MILES],
    'remaining_range_electric': ['mdi:ruler', LENGTH_MILES],
    'remaining_range_fuel': ['mdi:ruler', LENGTH_MILES],
    'max_range_electric': ['mdi:ruler', LENGTH_MILES],
    'remaining_fuel': ['mdi:gas-station', VOLUME_GALLONS],
    'charging_time_remaining': ['mdi:update', 'h'],
    'charging_status': ['mdi:battery-charging', None],
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the BMW sensors."""
    if hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
        attribute_info = ATTR_TO_HA_IMPERIAL
    else:
        attribute_info = ATTR_TO_HA_METRIC

    accounts = hass.data[BMW_DOMAIN]
    _LOGGER.debug('Found BMW accounts: %s',
                  ', '.join([a.name for a in accounts]))
    devices = []
    for account in accounts:
        for vehicle in account.account.vehicles:
            for attribute_name in vehicle.drive_train_attributes:
                device = BMWConnectedDriveSensor(
                    account, vehicle, attribute_name, attribute_info)
                devices.append(device)
            device = BMWConnectedDriveSensor(
                account, vehicle, 'mileage', attribute_info)
            devices.append(device)
    add_entities(devices, True)


class BMWConnectedDriveSensor(Entity):
    """Representation of a BMW vehicle sensor."""

    def __init__(self, account, vehicle, attribute: str, attribute_info):
        """Constructor."""
        self._vehicle = vehicle
        self._account = account
        self._attribute = attribute
        self._state = None
        self._name = '{} {}'.format(self._vehicle.name, self._attribute)
        self._unique_id = '{}-{}'.format(self._vehicle.vin, self._attribute)
        self._attribute_info = attribute_info

    @property
    def should_poll(self) -> bool:
        """Return False.

        Data update is triggered from BMWConnectedDriveEntity.
        """
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
        charging_state = vehicle_state.charging_status in [
            ChargingState.CHARGING]

        if self._attribute == 'charging_level_hv':
            return icon_for_battery_level(
                battery_level=vehicle_state.charging_level_hv,
                charging=charging_state)
        icon, _ = self._attribute_info.get(self._attribute, [None, None])
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
        _, unit = self._attribute_info.get(self._attribute, [None, None])
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
        elif self.unit_of_measurement == VOLUME_GALLONS:
            value = getattr(vehicle_state, self._attribute)
            value_converted = self.hass.config.units.volume(
                value, VOLUME_LITERS)
            self._state = round(value_converted)
        elif self.unit_of_measurement == LENGTH_MILES:
            value = getattr(vehicle_state, self._attribute)
            value_converted = self.hass.config.units.length(
                value, LENGTH_KILOMETERS)
            self._state = round(value_converted)
        else:
            self._state = getattr(vehicle_state, self._attribute)

    def update_callback(self):
        """Schedule a state update."""
        self.schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Add callback after being added to hass.

        Show latest data after startup.
        """
        self._account.add_update_listener(self.update_callback)
