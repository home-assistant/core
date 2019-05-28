"""Support for Honeywell Total Connect Comfort climate systems."""
import logging
import datetime

import requests
import voluptuous as vol
import somecomfort

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE, ATTR_FAN_MODES,
    ATTR_OPERATION_MODE, ATTR_OPERATION_LIST, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_AWAY_MODE, SUPPORT_OPERATION_MODE)
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, TEMP_CELSIUS, TEMP_FAHRENHEIT,
    ATTR_TEMPERATURE, CONF_REGION)

_LOGGER = logging.getLogger(__name__)

ATTR_FAN = 'fan'
ATTR_SYSTEM_MODE = 'system_mode'
ATTR_CURRENT_OPERATION = 'equipment_output_status'

CONF_AWAY_TEMPERATURE = 'away_temperature'
CONF_COOL_AWAY_TEMPERATURE = 'away_cool_temperature'
CONF_HEAT_AWAY_TEMPERATURE = 'away_heat_temperature'

DEFAULT_AWAY_TEMPERATURE = 16  # in C, for eu regions, the others are F/us
DEFAULT_COOL_AWAY_TEMPERATURE = 88
DEFAULT_HEAT_AWAY_TEMPERATURE = 61
DEFAULT_REGION = 'eu'
REGIONS = ['eu', 'us']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_AWAY_TEMPERATURE,
                 default=DEFAULT_AWAY_TEMPERATURE): vol.Coerce(float),
    vol.Optional(CONF_COOL_AWAY_TEMPERATURE,
                 default=DEFAULT_COOL_AWAY_TEMPERATURE): vol.Coerce(int),
    vol.Optional(CONF_HEAT_AWAY_TEMPERATURE,
                 default=DEFAULT_HEAT_AWAY_TEMPERATURE): vol.Coerce(int),
    vol.Optional(CONF_REGION, default=DEFAULT_REGION): vol.In(REGIONS),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Honeywell thermostat."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    region = config.get(CONF_REGION)

    if region == 'us':
        return _setup_us(username, password, config, add_entities)

    _LOGGER.warning(
        "The honeywell component is deprecated for EU (i.e. non-US) systems, "
        "this functionality will be removed in version 0.96. "
        "Please switch to the evohome component, "
        "see: https://home-assistant.io/components/evohome")


# config will be used later
def _setup_us(username, password, config, add_entities):
    """Set up the user."""
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

    add_entities([HoneywellUSThermostat(client, device, cool_away_temp,
                                        heat_away_temp, username, password)
                  for location in client.locations_by_id.values()
                  for device in location.devices_by_id.values()
                  if ((not loc_id or location.locationid == loc_id) and
                      (not dev_id or device.deviceid == dev_id))])
    return True


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
    def supported_features(self):
        """Return the list of supported features."""
        supported = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE)
        if hasattr(self._device, ATTR_SYSTEM_MODE):
            supported |= SUPPORT_OPERATION_MODE
        supported = (SUPPORT_FAN_MODE)
        return supported

    @property  # TODO: will need mapping of modes
    def fan_mode(self) -> Optional[str]:                                         # def is_fan_on(self):
        """Return the fan setting."""
        return self._device.fan_mode                                             #     return self._device.fan_running

    @property
    def fan_modes(self) -> Optional[List[str]]:
        """Return the list of available fan modes."""
        return somecomfort.FAN_MODES  # TODO: ['auto', 'on', 'circulate', 'follow schedule']

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        self._device.fan_mode = fan_mode

    @property
    def name(self) -> Optional[str]:
        """Return the name of the honeywell, if any."""
        return self._device.name

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return (TEMP_CELSIUS if self._device.temperature_unit == 'C'
                else TEMP_FAHRENHEIT)

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._device.current_temperature

    @property
    def current_humidity(self) -> Optional[int]:
        """Return the current humidity."""
        return self._device.current_humidity

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        if self._device.system_mode == 'cool':
            return self._device.setpoint_cool
        return self._device.setpoint_heat

    @property
    def hvac_mode(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        oper = getattr(self._device, ATTR_CURRENT_OPERATION, None)
        if oper == "off":
            oper = "idle"
        return oper

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
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
        data = {
            ATTR_FAN: (self.is_fan_on and 'running' or 'idle'),
            ATTR_FAN_MODE: self._device.fan_mode,
            ATTR_HVAC_MODE: self._device.system_mode,
        }
        data[ATTR_FAN_MODES] = somecomfort.FAN_MODES
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
        try:
            # Disabling all hold modes
            self._device.hold_cool = False
            self._device.hold_heat = False
        except somecomfort.SomeComfortError:
            _LOGGER.error('Can not stop hold mode')

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set the system mode (Cool, Heat, etc)."""
        if hasattr(self._device, ATTR_SYSTEM_MODE):
            self._device.system_mode = hvac_mode

    def update(self):
        """Update the state."""
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
