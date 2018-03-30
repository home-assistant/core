"""
Support for HomematicIP sensors.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.homematicip_cloud/
"""

import logging

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.homematicip_cloud import (
    HomematicipGenericDevice, DOMAIN, EVENT_HOME_CHANGED,
    ATTR_HOME_LABEL, ATTR_HOME_ID, ATTR_LOW_BATTERY, ATTR_RSSI)
from homeassistant.const import TEMP_CELSIUS, STATE_OK

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematicip_cloud']

ATTR_VALVE_STATE = 'valve_state'
ATTR_VALVE_POSITION = 'valve_position'
ATTR_TEMPERATURE_OFFSET = 'temperature_offset'

HMIP_UPTODATE = 'up_to_date'
HMIP_VALVE_DONE = 'adaption_done'
HMIP_SABOTAGE = 'sabotage'

STATE_LOW_BATTERY = 'low_battery'
STATE_SABOTAGE = 'sabotage'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the HomematicIP sensors devices."""
    # pylint: disable=import-error, no-name-in-module
    from homematicip.device import (
        HeatingThermostat, TemperatureHumiditySensorWithoutDisplay,
        TemperatureHumiditySensorDisplay)

    homeid = discovery_info['homeid']
    home = hass.data[DOMAIN][homeid]
    devices = [HomematicipAccesspoint(home)]

    for device in home.devices:
        devices.append(HomematicipDeviceStatus(home, device))
        if isinstance(device, HeatingThermostat):
            devices.append(HomematicipHeatingThermostat(home, device))
        if isinstance(device, TemperatureHumiditySensorWithoutDisplay):
            devices.append(HomematicipSensorThermometer(home, device))
            devices.append(HomematicipSensorHumidity(home, device))
        if isinstance(device, TemperatureHumiditySensorDisplay):
            devices.append(HomematicipSensorThermometer(home, device))
            devices.append(HomematicipSensorHumidity(home, device))

    if home.devices:
        add_devices(devices)


class HomematicipAccesspoint(Entity):
    """Representation of an HomeMaticIP access point."""

    def __init__(self, home):
        """Initialize the access point sensor."""
        self._home = home
        _LOGGER.debug('Setting up access point %s', home.label)

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, EVENT_HOME_CHANGED, self._home_changed)

    @callback
    def _home_changed(self, deviceid):
        """Handle device state changes."""
        if deviceid is None or deviceid == self._home.id:
            _LOGGER.debug('Event home %s', self._home.label)
            self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the access point device."""
        if self._home.label == '':
            return 'Access Point Status'
        return '{} Access Point Status'.format(self._home.label)

    @property
    def icon(self):
        """Return the icon of the access point device."""
        return 'mdi:access-point-network'

    @property
    def state(self):
        """Return the state of the access point."""
        return self._home.dutyCycle

    @property
    def available(self):
        """Device available."""
        return self._home.connected

    @property
    def device_state_attributes(self):
        """Return the state attributes of the access point."""
        return {
            ATTR_HOME_LABEL: self._home.label,
            ATTR_HOME_ID: self._home.id,
            }


class HomematicipDeviceStatus(HomematicipGenericDevice):
    """Representation of an HomematicIP device status."""

    def __init__(self, home, device):
        """Initialize the device."""
        super().__init__(home, device)
        _LOGGER.debug('Setting up sensor device status: %s', device.label)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name('Status')

    @property
    def icon(self):
        """Return the icon of the status device."""
        if (hasattr(self._device, 'sabotage') and
                self._device.sabotage == HMIP_SABOTAGE):
            return 'mdi:alert'
        elif self._device.lowBat:
            return 'mdi:battery-outline'
        elif self._device.updateState.lower() != HMIP_UPTODATE:
            return 'mdi:refresh'
        return 'mdi:check'

    @property
    def state(self):
        """Return the state of the generic device."""
        if (hasattr(self._device, 'sabotage') and
                self._device.sabotage == HMIP_SABOTAGE):
            return STATE_SABOTAGE
        elif self._device.lowBat:
            return STATE_LOW_BATTERY
        elif self._device.updateState.lower() != HMIP_UPTODATE:
            return self._device.updateState.lower()
        return STATE_OK


class HomematicipHeatingThermostat(HomematicipGenericDevice):
    """MomematicIP heating thermostat representation."""

    def __init__(self, home, device):
        """"Initialize heating thermostat."""
        super().__init__(home, device)
        _LOGGER.debug('Setting up heating thermostat device: %s', device.label)

    @property
    def icon(self):
        """Return the icon."""
        if self._device.valveState.lower() != HMIP_VALVE_DONE:
            return 'mdi:alert'
        return 'mdi:radiator'

    @property
    def state(self):
        """Return the state of the radiator valve."""
        if self._device.valveState.lower() != HMIP_VALVE_DONE:
            return self._device.valveState.lower()
        return round(self._device.valvePosition*100)

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return '%'

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_VALVE_STATE: self._device.valveState.lower(),
            ATTR_TEMPERATURE_OFFSET: self._device.temperatureOffset,
            ATTR_LOW_BATTERY: self._device.lowBat,
            ATTR_RSSI: self._device.rssiDeviceValue
        }


class HomematicipSensorHumidity(HomematicipGenericDevice):
    """MomematicIP thermometer device."""

    def __init__(self, home, device):
        """"Initialize the thermometer device."""
        super().__init__(home, device)
        _LOGGER.debug('Setting up humidity device: %s', device.label)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name('Humidity')

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:water'

    @property
    def state(self):
        """Return the state."""
        return self._device.humidity

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return '%'

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_LOW_BATTERY: self._device.lowBat,
            ATTR_RSSI: self._device.rssiDeviceValue,
        }


class HomematicipSensorThermometer(HomematicipGenericDevice):
    """MomematicIP thermometer device."""

    def __init__(self, home, device):
        """"Initialize the thermometer device."""
        super().__init__(home, device)
        _LOGGER.debug('Setting up thermometer device: %s', device.label)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name('Temperature')

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:thermometer'

    @property
    def state(self):
        """Return the state."""
        return self._device.actualTemperature

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return TEMP_CELSIUS

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_TEMPERATURE_OFFSET: self._device.temperatureOffset,
            ATTR_LOW_BATTERY: self._device.lowBat,
            ATTR_RSSI: self._device.rssiDeviceValue,
        }
