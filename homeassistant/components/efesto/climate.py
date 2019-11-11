"""Support for Efesto heating devices."""
import logging
import voluptuous as vol
import efestoclient

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_DEVICE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)

ATTR_DEVICE_STATUS = "device_status"
ATTR_HUMAN_DEVICE_STATUS = "human_device_status"
ATTR_REAL_POWER = "real_power"
ATTR_SMOKE_TEMP = "smoke_temperature"

DOMAIN = "Efesto"

FAN_1 = 1
FAN_2 = 2
FAN_3 = 3
FAN_4 = 4
FAN_5 = 5
FAN_MODES = [
    FAN_1,
    FAN_2,
    FAN_3,
    FAN_4,
    FAN_5,
]

CURRENT_HVAC_MAP_EFESTO_HEAT = {
    "ON": CURRENT_HVAC_HEAT,
    "CLEANING FIRE-POT": CURRENT_HVAC_HEAT,
    "FLAME LIGHT": CURRENT_HVAC_HEAT,
    "OFF": CURRENT_HVAC_OFF,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Efesto device."""
    url = config.get(CONF_URL)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    device = config.get(CONF_DEVICE)
    name = config.get(CONF_NAME)

    try:
        client = efestoclient.EfestoClient(url, username, password, device, False)
        add_entities([EfestoHeatingDevice(client, name, device)], True)
    except efestoclient.Error as err:
        _LOGGER.error("Error while connecting to the Efesto web service: %s", err)


class EfestoHeatingDevice(ClimateDevice):
    """Representation of a Efesto heating device."""

    def __init__(self, client, name, device_id):
        """Initialize the thermostat."""
        self.client = client
        self._device_id = device_id
        self._on = False
        self._device_status = None
        self._idle_info = None
        self._human_device_status = None
        self._current_temperature = None
        self._target_temperature = None
        self._smoke_temperature = None
        self._real_power = None
        self._current_power = None
        self._name = name if name else device_id

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        data = {
            ATTR_DEVICE_STATUS: self._device_status,
            ATTR_HUMAN_DEVICE_STATUS: self._human_device_status,
            ATTR_SMOKE_TEMP: self._smoke_temperature,
            ATTR_REAL_POWER: self._real_power,
        }
        return data

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._device_id

    @property
    def name(self):
        """Return the name of the Efesto, if any."""
        return self._name

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Efesto",
        }

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
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self._on:
            return HVAC_MODE_HEAT
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def fan_mode(self):
        """Return fan mode."""
        if self._current_power in FAN_MODES:
            return self._current_power
        return FAN_1

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return FAN_MODES

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self._human_device_status in CURRENT_HVAC_MAP_EFESTO_HEAT:
            return CURRENT_HVAC_MAP_EFESTO_HEAT.get(self._human_device_status)
        return CURRENT_HVAC_IDLE

    def turn_off(self):
        """Turn device off."""
        try:
            json = self.client.set_off()
            _LOGGER.debug("Turn off response: %s", json)
            if json["status"] > 0:
                _LOGGER.error("Failed to turn off device (%s)", json["message"])
        except ValueError:
            _LOGGER.error("Failed to turn off device")

    def turn_on(self):
        """Turn device on."""
        try:
            json = self.client.set_on()
            _LOGGER.debug("Turn on response: %s", json)
            if json["status"] > 0:
                _LOGGER.error("Failed to turn on device (%s)", json["message"])
        except ValueError:
            _LOGGER.error("Failed to turn on device")

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        json = self.client.set_temperature(round(temperature))
        _LOGGER.debug("Set temperature response: %s", json)
        if json["status"] > 0:
            _LOGGER.error("Failed to set temperature")

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if fan_mode is None:
            return
        json = self.client.set_power(fan_mode)
        _LOGGER.debug("Set fan (power) response: %s", json)
        if json["status"] > 0:
            _LOGGER.error("Failed to set fan (power)")

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_OFF:
            self.turn_off()
        elif hvac_mode == HVAC_MODE_HEAT:
            self.turn_on()

    def update(self):
        """Get the latest data."""
        try:
            json = self.client.get_status()
            _LOGGER.debug("Get status response: %s", json)

            if json["status"] != 0:
                _LOGGER.error("Update failed (%s)", json["message"])
                return

            self._device_status = json["deviceStatus"]

            if json["airTemperature"]:
                self._current_temperature = json["airTemperature"]
            if json["lastSetAirTemperature"]:
                self._target_temperature = json["lastSetAirTemperature"]
            if json["deviceStatusTranslated"]:
                self._human_device_status = json["deviceStatusTranslated"]
            if json["smokeTemperature"]:
                self._smoke_temperature = json["smokeTemperature"]
            if json["realPower"]:
                self._real_power = json["realPower"]
            if json["lastSetPower"]:
                self._current_power = json["lastSetPower"]

            if self._device_status == 0:
                self._on = False
            else:
                self._on = True
                if "idle_info" in json:
                    self._idle_info = json["idle_info"]
                    self._human_device_status = json["idle_info"]
                    if self._idle_info == "TURNING OFF":
                        self._on = False
        except ValueError:
            _LOGGER.error(
                "Update failed (wrong device id or no connection to Efesto server)"
            )
