"""Reads vehicle status from BMW connected drive portal."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import LENGTH_KILOMETERS

from . import DOMAIN as BMW_DOMAIN

DEPENDENCIES = ['bmw_connected_drive']

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    'lids': ['Doors', 'opening'],
    'windows': ['Windows', 'opening'],
    'door_lock_state': ['Door lock state', 'safety'],
    'lights_parking': ['Parking lights', 'light'],
    'condition_based_services': ['Condition based services', 'problem'],
    'check_control_messages': ['Control messages', 'problem']
}

SENSOR_TYPES_ELEC = {
    'charging_status': ['Charging status', 'power'],
    'connection_status': ['Connection status', 'plug']
}

SENSOR_TYPES_ELEC.update(SENSOR_TYPES)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the BMW sensors."""
    accounts = hass.data[BMW_DOMAIN]
    _LOGGER.debug('Found BMW accounts: %s',
                  ', '.join([a.name for a in accounts]))
    devices = []
    for account in accounts:
        for vehicle in account.account.vehicles:
            if vehicle.has_hv_battery:
                _LOGGER.debug('BMW with a high voltage battery')
                for key, value in sorted(SENSOR_TYPES_ELEC.items()):
                    device = BMWConnectedDriveSensor(
                        account, vehicle, key, value[0], value[1])
                    devices.append(device)
            elif vehicle.has_internal_combustion_engine:
                _LOGGER.debug('BMW with an internal combustion engine')
                for key, value in sorted(SENSOR_TYPES.items()):
                    device = BMWConnectedDriveSensor(
                        account, vehicle, key, value[0], value[1])
                    devices.append(device)
    add_entities(devices, True)


class BMWConnectedDriveSensor(BinarySensorDevice):
    """Representation of a BMW vehicle binary sensor."""

    def __init__(self, account, vehicle, attribute: str, sensor_name,
                 device_class):
        """Constructor."""
        self._account = account
        self._vehicle = vehicle
        self._attribute = attribute
        self._name = '{} {}'.format(self._vehicle.name, self._attribute)
        self._unique_id = '{}-{}'.format(self._vehicle.vin, self._attribute)
        self._sensor_name = sensor_name
        self._device_class = device_class
        self._state = None

    @property
    def should_poll(self) -> bool:
        """Return False.

        Data update is triggered from BMWConnectedDriveEntity.
        """
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the binary sensor."""
        return self._unique_id

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
            result['last_update_reason'] = vehicle_state.last_update_reason
        elif self._attribute == 'lights_parking':
            result['lights_parking'] = vehicle_state.parking_lights.value
        elif self._attribute == 'condition_based_services':
            for report in vehicle_state.condition_based_services:
                result.update(
                    self._format_cbs_report(report))
        elif self._attribute == 'check_control_messages':
            check_control_messages = vehicle_state.check_control_messages
            if not check_control_messages:
                result['check_control_messages'] = 'OK'
            else:
                cbs_list = []
                for message in check_control_messages:
                    cbs_list.append(message['ccmDescriptionShort'])
                result['check_control_messages'] = cbs_list
        elif self._attribute == 'charging_status':
            result['charging_status'] = vehicle_state.charging_status.value
            # pylint: disable=protected-access
            result['last_charging_end_result'] = \
                vehicle_state._attributes['lastChargingEndResult']
        if self._attribute == 'connection_status':
            # pylint: disable=protected-access
            result['connection_status'] = \
                vehicle_state._attributes['connectionStatus']

        return sorted(result.items())

    def update(self):
        """Read new state data from the library."""
        from bimmer_connected.state import LockState
        from bimmer_connected.state import ChargingState
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
        # device class light: On means light detected, Off means no light
        if self._attribute == 'lights_parking':
            self._state = vehicle_state.are_parking_lights_on
        # device class problem: On means problem detected, Off means no problem
        if self._attribute == 'condition_based_services':
            self._state = not vehicle_state.are_all_cbs_ok
        if self._attribute == 'check_control_messages':
            self._state = vehicle_state.has_check_control_messages
        # device class power: On means power detected, Off means no power
        if self._attribute == 'charging_status':
            self._state = vehicle_state.charging_status in \
                          [ChargingState.CHARGING]
        # device class plug: On means device is plugged in,
        #                    Off means device is unplugged
        if self._attribute == 'connection_status':
            # pylint: disable=protected-access
            self._state = (vehicle_state._attributes['connectionStatus'] ==
                           'CONNECTED')

    def _format_cbs_report(self, report):
        result = {}
        service_type = report.service_type.lower().replace('_', ' ')
        result['{} status'.format(service_type)] = report.state.value
        if report.due_date is not None:
            result['{} date'.format(service_type)] = \
                report.due_date.strftime('%Y-%m-%d')
        if report.due_distance is not None:
            distance = round(self.hass.config.units.length(
                report.due_distance, LENGTH_KILOMETERS))
            result['{} distance'.format(service_type)] = '{} {}'.format(
                distance, self.hass.config.units.length_unit)
        return result

    def update_callback(self):
        """Schedule a state update."""
        self.schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Add callback after being added to hass.

        Show latest data after startup.
        """
        self._account.add_update_listener(self.update_callback)
