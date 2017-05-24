"""
Support for Honeywell Round Connected and Honeywell Evohome thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.honeywell/
"""
import logging
import socket
import datetime

import requests
import voluptuous as vol

from homeassistant.components.climate import (
    ClimateDevice, PLATFORM_SCHEMA, ATTR_FAN_MODE, ATTR_FAN_LIST,
    ATTR_OPERATION_MODE, ATTR_OPERATION_LIST)
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, TEMP_CELSIUS, TEMP_FAHRENHEIT,
    ATTR_TEMPERATURE)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['evohomeclient==0.2.5',
                'somecomfort==0.4.1']

_LOGGER = logging.getLogger(__name__)

ATTR_FAN = 'fan'
ATTR_SYSTEM_MODE = 'system_mode'
ATTR_CURRENT_OPERATION = 'equipment_output_status'

CONF_AWAY_TEMPERATURE = 'away_temperature'
CONF_COOL_AWAY_TEMPERATURE = 'away_cool_temperature'
CONF_HEAT_AWAY_TEMPERATURE = 'away_heat_temperature'
CONF_REGION = 'region'

DEFAULT_AWAY_TEMPERATURE = 16
DEFAULT_COOL_AWAY_TEMPERATURE = 30
DEFAULT_HEAT_AWAY_TEMPERATURE = 16
DEFAULT_REGION = 'eu'
REGIONS = ['eu', 'us']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_AWAY_TEMPERATURE,
                 default=DEFAULT_AWAY_TEMPERATURE): vol.Coerce(float),
    vol.Optional(CONF_COOL_AWAY_TEMPERATURE,
                 default=DEFAULT_COOL_AWAY_TEMPERATURE): vol.Coerce(float),
    vol.Optional(CONF_HEAT_AWAY_TEMPERATURE,
                 default=DEFAULT_HEAT_AWAY_TEMPERATURE): vol.Coerce(float),
    vol.Optional(CONF_REGION, default=DEFAULT_REGION): vol.In(REGIONS),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Honeywell thermostat."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    region = config.get(CONF_REGION)

    if region == 'us':
        return _setup_us(username, password, config, add_devices)
    else:
        return _setup_round(username, password, config, add_devices)


def _setup_round(username, password, config, add_devices):
    """Set up the rounding function."""
    from evohomeclient import EvohomeClient

    away_temp = config.get(CONF_AWAY_TEMPERATURE)
    evo_api = EvohomeClient(username, password)

    try:
        zones = evo_api.temperatures(force_refresh=True)
        for i, zone in enumerate(zones):
            add_devices(
                [RoundThermostat(evo_api, zone['id'], i == 0, away_temp)]
            )
    except socket.error:
        _LOGGER.error(
            "Connection error logging into the honeywell evohome web service")
        return False
    return True


# config will be used later
def _setup_us(username, password, config, add_devices):
    """Set up the user."""
    import somecomfort

    try:
        client = somecomfort.SomeComfort(username, password)
    except somecomfort.AuthError:
        _LOGGER.error("Failed to login to honeywell account %s", username)
        return False
    except somecomfort.SomeComfortError as ex:
        _LOGGER.error("Failed to initialize honeywell client: %s", str(ex))
        return False

    dev_id = config.get('thermostat')
    loc_id = config.get('location')
    cool_away_temp = config.get(CONF_COOL_AWAY_TEMPERATURE)
    heat_away_temp = config.get(CONF_HEAT_AWAY_TEMPERATURE)

    add_devices([HoneywellUSThermostat(client, device, cool_away_temp,
                                       heat_away_temp, username, password)
                 for location in client.locations_by_id.values()
                 for device in location.devices_by_id.values()
                 if ((not loc_id or location.locationid == loc_id) and
                     (not dev_id or device.deviceid == dev_id))])
    return True


class RoundThermostat(ClimateDevice):
    """Representation of a Honeywell Round Connected thermostat."""

    def __init__(self, device, zone_id, master, away_temp):
        """Initialize the thermostat."""
        self.device = device
        self._current_temperature = None
        self._target_temperature = None
        self._name = 'round connected'
        self._id = zone_id
        self._master = master
        self._is_dhw = False
        self._away_temp = away_temp
        self._away = False
        self.update()

    @property
    def name(self):
        """Return the name of the honeywell, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._is_dhw:
            return None
        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self.device.set_temperature(self._name, temperature)

    @property
    def current_operation(self: ClimateDevice) -> str:
        """Get the current operation of the system."""
        return getattr(self.device, ATTR_SYSTEM_MODE, None)

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._away

    def set_operation_mode(self: ClimateDevice, operation_mode: str) -> None:
        """Set the HVAC mode for the thermostat."""
        if hasattr(self.device, ATTR_SYSTEM_MODE):
            self.device.system_mode = operation_mode

    def turn_away_mode_on(self):
        """Turn away on.

        Honeywell does have a proprietary away mode, but it doesn't really work
        the way it should. For example: If you set a temperature manually
        it doesn't get overwritten when away mode is switched on.
        """
        self._away = True
        self.device.set_temperature(self._name, self._away_temp)

    def turn_away_mode_off(self):
        """Turn away off."""
        self._away = False
        self.device.cancel_temp_override(self._name)

    def update(self):
        """Get the latest date."""
        try:
            # Only refresh if this is the "master" device,
            # others will pick up the cache
            for val in self.device.temperatures(force_refresh=self._master):
                if val['id'] == self._id:
                    data = val

        except StopIteration:
            _LOGGER.error("Did not receive any temperature data from the "
                          "evohomeclient API")
            return

        self._current_temperature = data['temp']
        self._target_temperature = data['setpoint']
        if data['thermostat'] == 'DOMESTIC_HOT_WATER':
            self._name = 'Hot Water'
            self._is_dhw = True
        else:
            self._name = data['name']
            self._is_dhw = False


class HoneywellUSThermostat(ClimateDevice):
    """Representation of a Honeywell US Thermostat."""

    def __init__(self, client, device, cool_away_temp,
                 heat_away_temp, username, password):
        """Initialize the thermostat."""
        self._client = client
        self._device = device
        self._cool_away_temp = cool_away_temp
        self._heat_away_temp = heat_away_temp
        self._away = False
        self._username = username
        self._password = password

    @property
    def is_fan_on(self):
        """Return true if fan is on."""
        return self._device.fan_running

    @property
    def name(self):
        """Return the name of the honeywell, if any."""
        return self._device.name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return (TEMP_CELSIUS if self._device.temperature_unit == 'C'
                else TEMP_FAHRENHEIT)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._device.system_mode == 'cool':
            return self._device.setpoint_cool
        else:
            return self._device.setpoint_heat

    @property
    def current_operation(self: ClimateDevice) -> str:
        """Return current operation ie. heat, cool, idle."""
        oper = getattr(self._device, ATTR_CURRENT_OPERATION, None)
        if oper == "off":
            oper = "idle"
        return oper

    def set_temperature(self, **kwargs):
        """Set target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        import somecomfort
        try:
            # Get current mode
            mode = self._device.system_mode
            # Set hold if this is not the case
            if getattr(self._device, "hold_{}".format(mode)) is False:
                # Get next period key
                next_period_key = '{}NextPeriod'.format(mode.capitalize())
                # Get next period raw value
                next_period = self._device.raw_ui_data.get(next_period_key)
                # Get next period time
                hour, minute = divmod(next_period * 15, 60)
                # Set hold time
                setattr(self._device,
                        "hold_{}".format(mode),
                        datetime.time(hour, minute))
            # Set temperature
            setattr(self._device,
                    "setpoint_{}".format(mode),
                    temperature)
        except somecomfort.SomeComfortError:
            _LOGGER.error("Temperature %.1f out of range", temperature)

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        import somecomfort
        data = {
            ATTR_FAN: (self.is_fan_on and 'running' or 'idle'),
            ATTR_FAN_MODE: self._device.fan_mode,
            ATTR_OPERATION_MODE: self._device.system_mode,
        }
        data[ATTR_FAN_LIST] = somecomfort.FAN_MODES
        data[ATTR_OPERATION_LIST] = somecomfort.SYSTEM_MODES
        return data

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._away

    def turn_away_mode_on(self):
        """Turn away on.

        Somecomfort does have a proprietary away mode, but it doesn't really
        work the way it should. For example: If you set a temperature manually
        it doesn't get overwritten when away mode is switched on.
        """
        self._away = True
        import somecomfort
        try:
            # Get current mode
            mode = self._device.system_mode
        except somecomfort.SomeComfortError:
            _LOGGER.error('Can not get system mode')
            return
        try:

            # Set permanent hold
            setattr(self._device,
                    "hold_{}".format(mode),
                    True)
            # Set temperature
            setattr(self._device,
                    "setpoint_{}".format(mode),
                    getattr(self, "_{}_away_temp".format(mode)))
        except somecomfort.SomeComfortError:
            _LOGGER.error('Temperature %.1f out of range',
                          getattr(self, "_{}_away_temp".format(mode)))

    def turn_away_mode_off(self):
        """Turn away off."""
        self._away = False
        import somecomfort
        try:
            # Disabling all hold modes
            self._device.hold_cool = False
            self._device.hold_heat = False
        except somecomfort.SomeComfortError:
            _LOGGER.error('Can not stop hold mode')

    def set_operation_mode(self: ClimateDevice, operation_mode: str) -> None:
        """Set the system mode (Cool, Heat, etc)."""
        if hasattr(self._device, ATTR_SYSTEM_MODE):
            self._device.system_mode = operation_mode

    def update(self):
        """Update the state."""
        import somecomfort
        retries = 3
        while retries > 0:
            try:
                self._device.refresh()
                break
            except (somecomfort.client.APIRateLimited, OSError,
                    requests.exceptions.ReadTimeout) as exp:
                retries -= 1
                if retries == 0:
                    raise exp
                if not self._retry():
                    raise exp
                _LOGGER.error(
                    "SomeComfort update failed, Retrying - Error: %s", exp)

    def _retry(self):
        """Recreate a new somecomfort client.

        When we got an error, the best way to be sure that the next query
        will succeed, is to recreate a new somecomfort client.
        """
        import somecomfort
        try:
            self._client = somecomfort.SomeComfort(
                self._username, self._password)
        except somecomfort.AuthError:
            _LOGGER.error("Failed to login to honeywell account %s",
                          self._username)
            return False
        except somecomfort.SomeComfortError as ex:
            _LOGGER.error("Failed to initialize honeywell client: %s",
                          str(ex))
            return False

        devices = [device
                   for location in self._client.locations_by_id.values()
                   for device in location.devices_by_id.values()
                   if device.name == self._device.name]

        if len(devices) != 1:
            _LOGGER.error("Failed to find device %s", self._device.name)
            return False

        self._device = devices[0]
        return True
