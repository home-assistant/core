"""Support for Efesto heating devices."""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    SUPPORT_ON_OFF, ATTR_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_URL, CONF_PASSWORD, CONF_USERNAME, CONF_DEVICE,
    PRECISION_WHOLE, STATE_OFF, STATE_ON, TEMP_CELSIUS
)

REQUIREMENTS = ['efestoclient==0.0.7']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_DEVICE): cv.string,
})

ATTR_DEVICE_STATUS = 'device_status'
ATTR_SMOKE_TEMP = 'smoke_temperature'
ATTR_REAL_POWER = 'real_power'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Efesto device."""
    url = config.get(CONF_URL)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    device = config.get(CONF_DEVICE)

    return _setup_efesto(
        url, username, password, device, config, add_entities
    )


def _setup_efesto(url, username, password, device, config, add_entities):
    """Set up the rounding function."""
    from efestoclient import EfestoClient

    client = EfestoClient(url, username, password, device, False)

    add_entities(
        [EfestoHeatingDevice(client)],
        True
    )

    return True


class EfestoHeatingDevice(ClimateDevice):
    """Representation of a Efesto heating device."""

    def __init__(self, client):
        """Initialize the thermostat."""
        self.client = client
        self._on = False
        self._device_status = None
        self._idle_info = None
        self._operation_mode = None
        self._current_temperature = None
        self._target_temperature = None
        self._smoke_temperature = None
        self._real_power = None
        self._name = 'Efesto'

    @property
    def supported_features(self):
        """Return the list of supported features."""
        supported = (
            SUPPORT_TARGET_TEMPERATURE | SUPPORT_ON_OFF
        )
        return supported

    @property
    def state(self):
        """Return the current state."""
        if (self._operation_mode and
                self._operation_mode not in ['OFF', 'ON']):
            return self._operation_mode
        if self.is_on is False:
            return STATE_OFF
        if self.is_on:
            return STATE_ON
        return None

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        data = {
            ATTR_DEVICE_STATUS: self._device_status,
            ATTR_SMOKE_TEMP: self._smoke_temperature,
            ATTR_REAL_POWER: self._real_power,
            ATTR_OPERATION_MODE: self._operation_mode,
        }
        return data

    @property
    def name(self):
        """Return the name of the Efesto, if any."""
        return self._name

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return PRECISION_WHOLE

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def is_on(self):
        """Return true if on."""
        return self._on

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def turn_off(self):
        """Turn device off."""
        try:
            json = self.client.set_off()
            _LOGGER.debug("JSON OUTPUT: %s", json)
            if json['status'] > 0:
                _LOGGER.error("Failed to turn off device (%s)",
                              json['message'])
                return

        except ValueError:
            _LOGGER.error("Failed to turn off device")
            return

    def turn_on(self):
        """Turn device on."""
        try:
            json = self.client.set_on()
            _LOGGER.debug("JSON OUTPUT: %s", json)
            if json['status'] > 0:
                _LOGGER.error("Failed to turn on device (%s)", json['message'])
                return

        except ValueError:
            _LOGGER.error("Failed to turn on device")
            return

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        res = self.client.set_temperature(round(temperature))
        if res['status'] > 0:
            _LOGGER.error("Failed to set temperature")
            return

    def update(self):
        """Get the latest data."""
        try:
            json = self.client.get_status()
            _LOGGER.debug("JSON OUTPUT: %s", json)

            if json['status'] == 0:
                self._device_status = json['deviceStatus']
                if self._device_status == 0:
                    self._on = False
                else:
                    self._on = True
                    if 'idle_info' in json:
                        self._idle_info = json['idle_info']
                        if self._idle_info == "TURNING OFF":
                            self._on = False

                if json['airTemperature']:
                    self._current_temperature = json['airTemperature']
                if json['lastSetAirTemperature']:
                    self._target_temperature = json['lastSetAirTemperature']
                if json['deviceStatusTranslated']:
                    self._operation_mode = json['deviceStatusTranslated']
                if json['smokeTemperature']:
                    self._smoke_temperature = json['smokeTemperature']
                if json['realPower']:
                    self._real_power = json['realPower']
            else:
                _LOGGER.error(
                    "Update failed (%s)", json['message']
                )

        except ValueError:
            _LOGGER.error(
                "Update failed (wrong device id or no connection "
                "to Efesto server)"
            )
