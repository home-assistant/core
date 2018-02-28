"""
Support for HomematicIP sensors.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homematicip/
"""

import logging

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.components.homematicip import (DOMAIN,
                                                  EVENT_HOME_CHANGED,
                                                  EVENT_DEVICE_CHANGED)

REQUIREMENTS = ['homematicip==0.8']

_LOGGER = logging.getLogger(__name__)

ATTR_ID = 'device_id'
ATTR_HOME_ID = 'home_id'
ATTR_HOME = 'home'
ATTR_LABEL = 'label'
ATTR_LASTSTATUS_UPDATE = 'last_status_update'
ATTR_FIRMWARE = 'status_firmware'
ATTR_ACTUAL_FIRMWARE = 'actual_firmware'
ATTR_AVAILABLE_FIRMWARE = 'available_firmware'
ATTR_LOW_BATTERY = 'low_battery'
ATTR_UNREACHABLE = 'not_reachable'
ATTR_SABOTAGE = 'sabotage'
ATTR_UPTODATE = 'up_to_date'
ATTR_RSSI_DEVICE = 'rssi_device'
ATTR_RSSI_PEER = 'rssi_peer'
ATTR_WINDOW = 'window'
ATTR_ON = 'on'
ATTR_EVENT_DELAY = 'event_delay'
ATTR_VALVE_STATE = 'valve_state'
ATTR_VALVE_POSITION = 'valve_position'
ATTR_TEMPERATURE_OFFSET = 'temperature_offset'

ATTR_CONNECTED = 'connected'
ATTR_DUTYCYCLE = 'dutycycle'
ATTR_CURRENT_APVERSION = 'current_apversion'
ATTR_AVAILABLE_APVERSION = 'available_apversion'
ATTR_TIMEZONE_ID = 'timezone_id'
ATTR_PIN_ASSIGNED = 'pin_assigned'
ATTR_UPDATE_STATE = 'update_state'
ATTR_APEXCHANGE_CLIENTID = 'apexchange_clientid'
ATTR_APEXCHANGE_STATE = 'apexchange_state'
ATTR_ACCESSPOINT = 'accesspoint'

HMIP_UPTODATE = 'up_to_date'
HMIP_VALVE_DONE = 'adaption_done'
HMIP_SABOTAGE = 'sabotage'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the HomematicIP sensors devices."""
    # pylint: disable=import-error, no-name-in-module
    from homematicip.device import (HeatingThermostat,
                                    TemperatureHumiditySensorWithoutDisplay,
                                    TemperatureHumiditySensorDisplay)

    _LOGGER.info('Setting up HomeMaticIP accespoint & generic devices')
    homeid = discovery_info['homeid']
    home = hass.data[DOMAIN][homeid]
    add_devices([HomematicipAccesspoint(hass, home)])
    if home.devices is None:
        return False
    for device in home.devices:
        add_devices([HomematicipDeviceStatus(hass, home, device)])
        if isinstance(device, HeatingThermostat):
            add_devices([HomematicipHeatingThermostat(hass, home, device)])
        if isinstance(device, TemperatureHumiditySensorWithoutDisplay):
            add_devices([HomematicipSensorThermometer(hass, home, device)])
            add_devices([HomematicipSensorHumidity(hass, home, device)])
        if isinstance(device, TemperatureHumiditySensorDisplay):
            add_devices([HomematicipSensorThermometer(hass, home, device)])
            add_devices([HomematicipSensorHumidity(hass, home, device)])
    return True


class HomematicipGenericDevice(Entity):
    """Representation of an HomematicIP generic device."""

    def __init__(self, hass, home, device, signal=None):
        """Initialize the generic device."""
        self.hass = hass
        self._home = home
        self._device = device

        @callback
        def event_device(event):
            """Handle device state changes."""
            _LOGGER.debug('Event Device: %s', self._device.label)
            self.schedule_update_ha_state(True)

        hass.bus.listen(EVENT_DEVICE_CHANGED, event_device)

    def _name(self, addon=''):
        """Return the name of the device."""
        name = ''
        if self._home.label != '':
            name += self._home.label + ' '
        name += self._device.label
        if addon != '':
            name += ' ' + addon
        return name

    @property
    def name(self):
        """Return the name of the generic device."""
        return self._name()

    @property
    def icon(self):
        """Return the icon of the generic device."""
        return 'mdi:hexagon-outline'

    @property
    def state(self):
        """Return the state of the generic device."""
        return 'empty'

    @property
    def force_update(self):
        """Force update."""
        return True

    @property
    def should_poll(self):
        """No polling needed."""
        return True

    @property
    def available(self):
        """Device available."""
        return True

    def _generic_state_attributes(self):
        """Return the state attributes of the generic device."""
        attr = {}
        if hasattr(self._home.label, 'label'):
            attr.update({ATTR_HOME: self._home.label})
        if hasattr(self._device, 'label'):
            attr.update({ATTR_LABEL: self._device.label})
        if hasattr(self._device, 'lastStatusUpdate'):
            last = self._device.lastStatusUpdate
            if last is not None:
                attr.update({ATTR_LASTSTATUS_UPDATE:
                             last.isoformat()})
        if hasattr(self._device, 'homeId'):
            attr.update({ATTR_HOME_ID: self._device.homeId})
        if hasattr(self._device, 'id'):
            attr.update({ATTR_ID: self._device.id.lower()})
        if hasattr(self._device, 'updateState'):
            attr.update({ATTR_FIRMWARE: self._device.updateState.lower()})
        if hasattr(self._device, 'firmwareVersion'):
            attr.update({ATTR_ACTUAL_FIRMWARE: self._device.firmwareVersion})
        if hasattr(self._device, 'availableFirmwareVersion'):
            attr.update({ATTR_AVAILABLE_FIRMWARE:
                         self._device.availableFirmwareVersion})
        if hasattr(self._device, 'lowBat'):
            attr.update({ATTR_LOW_BATTERY: self._device.lowBat})
        if hasattr(self._device, 'unreach'):
            attr.update({ATTR_UNREACHABLE: self._device.unreach})
        if hasattr(self._device, 'sabotage'):
            attr.update({ATTR_SABOTAGE: self._device.sabotage})
        if hasattr(self._device, 'rssiDeviceValue'):
            attr.update({ATTR_RSSI_DEVICE: self._device.rssiDeviceValue})
        if hasattr(self._device, 'rssiPeerValue'):
            attr.update({ATTR_RSSI_PEER: self._device.rssiPeerValue})
        return attr

    @property
    def device_state_attributes(self):
        """Return the state attributes of the generic device."""
        return self._generic_state_attributes()


class HomematicipAccesspoint(HomematicipGenericDevice):
    """Representation of an HomeMaticIP access point."""

    def __init__(self, hass, home):
        """Initialize the access point sensor."""
        super().__init__(hass, home, home)

        @callback
        def event_home(event):
            """Handle device state changes."""
            _LOGGER.debug('Event Access Point: %s', self._home.label)
            self.async_schedule_update_ha_state(True)

        hass.bus.listen(EVENT_HOME_CHANGED, event_home)

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
    def device_state_attributes(self):
        """Return the state attributes of the access point."""
        return {
            ATTR_LABEL: self._home.label,
            ATTR_ID: self._home.id,
            ATTR_CONNECTED: self._home.connected,
            ATTR_DUTYCYCLE: self._home.dutyCycle,
            ATTR_CURRENT_APVERSION: self._home.currentAPVersion,
            ATTR_AVAILABLE_APVERSION: self._home.availableAPVersion,
            ATTR_TIMEZONE_ID: self._home.timeZoneId,
            ATTR_PIN_ASSIGNED: self._home.pinAssigned,
            ATTR_UPDATE_STATE: self._home.updateState,
            ATTR_APEXCHANGE_CLIENTID: self._home.apExchangeClientId,
            ATTR_APEXCHANGE_STATE: self._home.apExchangeState,
            }


class HomematicipDeviceStatus(HomematicipGenericDevice):
    """Representation of an HomematicIP sensor device."""

    def __init__(self, hass, home, device, signal=None):
        """Initialize the device."""
        super().__init__(hass, home, device)
        _LOGGER.debug('Setting up sensor device status: %s',
                      device.label)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name('Status')

    @property
    def icon(self):
        """Return the icon of the generic device."""
        if self._device.unreach is None or self._device.unreach:
            return 'mdi:wifi-off'
        elif self._device.lowBat:
            return 'mdi:battery-outline'
        elif (hasattr(self._device, 'sabotage') and
              self._device.sabotage == HMIP_SABOTAGE):
            return 'mdi:alert'
        elif self._device.updateState.lower() != HMIP_UPTODATE:
            return 'mdi:refresh'
        return 'mdi:check'

    @property
    def state(self):
        """Return the state of the generic device."""
        if self._device.unreach is None or self._device.unreach:
            return ATTR_UNREACHABLE
        elif self._device.lowBat:
            return ATTR_LOW_BATTERY
        elif (hasattr(self._device, 'sabotage') and
              self._device.sabotage == HMIP_SABOTAGE):
            return ATTR_SABOTAGE
        elif self._device.updateState.lower() != HMIP_UPTODATE:
            return self._device.updateState.lower()
        return 'OK'

    def _sensor_state_attributes(self):
        """Return the state attributes of the generic device."""
        attr = self._generic_state_attributes()

        if hasattr(self._device, 'on'):
            attr.update({ATTR_ON: self._device.on})
        if hasattr(self._device, 'currentPowerConsumption'):
            attr.update({'currentPowerConsumption':
                         self._device.currentPowerConsumption})
        return attr

    @property
    def device_state_attributes(self):
        """Return the state attributes of the generic device."""
        return self._generic_state_attributes()


class HomematicipHeatingThermostat(HomematicipGenericDevice):
    """MomematicIP heating thermostat representation."""

    def __init__(self, hass, home, device):
        """"Initialize heating thermostat."""
        super().__init__(hass, home, device)
        _LOGGER.debug('Setting up heating thermostat device: %s',
                      device.label)

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
        return "{}%".format(round(self._device.valvePosition*100))

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = self._generic_state_attributes()
        if hasattr(self._device, 'valveState'):
            attr.update({ATTR_VALVE_STATE: self._device.valveState.lower()})
        if hasattr(self._device, 'valvePosition'):
            attr.update({ATTR_VALVE_POSITION: self._device.valvePosition})
        if hasattr(self._device, 'temperatureOffset'):
            attr.update({ATTR_TEMPERATURE_OFFSET:
                         self._device.temperatureOffset})
        return attr


class HomematicipSensorHumidity(HomematicipGenericDevice):
    """MomematicIP thermometer device."""

    def __init__(self, hass, home, device):
        """"Initialize the thermometer device."""
        super().__init__(hass, home, device)
        _LOGGER.debug('Setting up heating thermostat device: %s',
                      device.label)

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
        return "{} %".format(self._device.humidity)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = self._generic_state_attributes()
        return attr


class HomematicipSensorThermometer(HomematicipGenericDevice):
    """MomematicIP thermometer device."""

    def __init__(self, hass, home, device):
        """"Initialize the thermometer device."""
        super().__init__(hass, home, device)
        _LOGGER.debug('Setting up heating thermostat device: %s',
                      device.label)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name('Thermometer')

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:thermometer'

    @property
    def state(self):
        """Return the state."""
        return "{}°C".format(self._device.actualTemperature)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = self._generic_state_attributes()
        return attr


class HomematicipShutterContact(HomematicipGenericDevice):
    """MomematicIP shutter contact."""

    def __init__(self, hass, home, device):
        """"Initialize the shutter contact."""
        super().__init__(self, hass, home, device)
        _LOGGER.debug('Setting up shutter contact device: %s',
                      device.label)

    @property
    def icon(self):
        """Return the icon."""
        if self._device.sabotage.lower() != HMIP_SABOTAGE:
            return 'mdi:alert'
        return 'mdi:pause'

    @property
    def state(self):
        """Return the state."""
        if self._device.sabotage.lower() != HMIP_SABOTAGE:
            return self._device.sabotage.lower()
        return self._device.windowState

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = self._generic_state_attributes()
        attr.update({ATTR_WINDOW: self._device.windowState.lower()})
        attr.update({ATTR_EVENT_DELAY: self._device.eventDelay.lower()})
        return attr
