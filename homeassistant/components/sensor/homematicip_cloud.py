"""
Support for HomematicIP sensors.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.homematicip_cloud/
"""

import logging

from homeassistant.components.homematicip_cloud import (
    HomematicipGenericDevice, DOMAIN,
    ATTR_HOME_NAME, ATTR_HOME_ID, ATTR_LOW_BATTERY, ATTR_DEVICE_RSSI,
    ATTR_CONNECTED, ATTR_DUTY_CYCLE)
from homeassistant.const import TEMP_CELSIUS

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematicip_cloud']

ATTR_VALVE_STATE = 'valve_state'
ATTR_VALVE_POSITION = 'valve_position'
ATTR_TEMPERATURE = 'temperature'
ATTR_TEMPERATURE_OFFSET = 'temperature_offset'
ATTR_HUMIDITY = 'humidity'

HMIP_UPTODATE = 'up_to_date'
HMIP_VALVE_DONE = 'adaption_done'
HMIP_SABOTAGE = 'sabotage'

STATE_OK = 'OK'
STATE_LOW_BATTERY = 'Low_battery'
STATE_SABOTAGE = 'Sabotage'


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the HomematicIP sensors devices."""

    from homematicip.device import (
        HeatingThermostat, TemperatureHumiditySensorWithoutDisplay,
        TemperatureHumiditySensorDisplay)

    home = hass.data[DOMAIN][discovery_info[ATTR_HOME_ID]]
    devices = [HomematicipAccesspointStatus(home)]

    for device in home.devices:
        devices.append(HomematicipDeviceStatus(home, device))
        if isinstance(device, HeatingThermostat):
            devices.append(HomematicipHeatingThermostat(home, device))
        if isinstance(device, TemperatureHumiditySensorWithoutDisplay):
            devices.append(HomematicipTemperatureSensor(home, device))
            devices.append(HomematicipHumiditySensor(home, device))
        if isinstance(device, TemperatureHumiditySensorDisplay):
            devices.append(HomematicipTemperatureSensor(home, device))
            devices.append(HomematicipHumiditySensor(home, device))

    if home.devices:
        async_add_devices(devices)


class HomematicipAccesspointStatus(HomematicipGenericDevice):
    """Representation of an HomeMaticIP access point."""

    def __init__(self, home, post='Status'):
        """"Initialize access point device."""
        self.post = post
        super().__init__(home, home)

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
            ATTR_HOME_NAME: self._home.name,
            ATTR_CONNECTED: self._home.connected,
            ATTR_DUTY_CYCLE: self._home.dutyCycle,
            }


class HomematicipDeviceStatus(HomematicipGenericDevice):
    """Representation of an HomematicIP device status."""

    def __init__(self, home, device):
        """"Initialize generic status device."""
        super().__init__(home, device, 'Status')

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
            return self._device.updateState.capitalize()
        return STATE_OK


class HomematicipHeatingThermostat(HomematicipGenericDevice):
    """MomematicIP heating thermostat representation."""

    def __init__(self, home, device):
        """"Initialize heating thermostat device."""
        super().__init__(home, device, 'Heating')

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
            return self._device.valveState.capitalize()
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
            ATTR_VALVE_POSITION: round(self._device.valvePosition*100),
            ATTR_TEMPERATURE_OFFSET: self._device.temperatureOffset,
            ATTR_LOW_BATTERY: self._device.lowBat,
            ATTR_DEVICE_RSSI: self._device.rssiDeviceValue
        }


class HomematicipHumiditySensor(HomematicipGenericDevice):
    """MomematicIP humidity device."""

    def __init__(self, home, device):
        """"Initialize the thermometer device."""
        super().__init__(home, device, 'Humidity')

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:water-percent'

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
            ATTR_HUMIDITY: self._device.humidity,
            ATTR_LOW_BATTERY: self._device.lowBat,
            ATTR_DEVICE_RSSI: self._device.rssiDeviceValue,
        }


class HomematicipTemperatureSensor(HomematicipGenericDevice):
    """MomematicIP the thermometer device."""

    def __init__(self, home, device):
        """"Initialize the thermometer device."""
        super().__init__(home, device, 'Temperature')

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
            ATTR_TEMPERATURE: self._device.actualTemperature,
            ATTR_TEMPERATURE_OFFSET: self._device.temperatureOffset,
            ATTR_LOW_BATTERY: self._device.lowBat,
            ATTR_DEVICE_RSSI: self._device.rssiDeviceValue,
        }
