"""Viessmann ViCare water_heater device."""
import logging

import voluptuous as vol
from PyViCare.PyViCareDevice import Device

from homeassistant.components.water_heater import (
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterDevice,
)

from homeassistant.const import (
    TEMP_CELSIUS,
    ATTR_TEMPERATURE,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_NAME,
    PRECISION_WHOLE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ["PyViCare==0.1.0"]

CONF_CIRCUIT = "circuit"

VICARE_MODE_DHW = "dhw"
VICARE_MODE_DHWANDHEATING = "dhwAndHeating"
VICARE_MODE_FORCEDREDUCED = "forcedReduced"
VICARE_MODE_FORCEDNORMAL = "forcedNormal"
VICARE_MODE_OFF = "standby"

VICARE_TEMP_WATER_MIN = 10
VICARE_TEMP_WATER_MAX = 60

OPERATION_MODE_ON = "on"
OPERATION_MODE_OFF = "off"

SUPPORT_FLAGS_HEATER = SUPPORT_TARGET_TEMPERATURE

VICARE_TO_HA_HVAC_DHW = {
    VICARE_MODE_DHW: OPERATION_MODE_ON,
    VICARE_MODE_DHWANDHEATING: OPERATION_MODE_ON,
    VICARE_MODE_FORCEDREDUCED: OPERATION_MODE_OFF,
    VICARE_MODE_FORCEDNORMAL: OPERATION_MODE_ON,
    VICARE_MODE_OFF: OPERATION_MODE_OFF,
}

HA_TO_VICARE_HVAC_DHW = {
    OPERATION_MODE_OFF: VICARE_MODE_OFF,
    OPERATION_MODE_ON: VICARE_MODE_DHW,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CIRCUIT): int,
        vol.Optional(CONF_NAME, default="ViCare"): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the ViCare water_heater devices."""
    if config.get(CONF_CIRCUIT) is None:
        vicare_api = Device(
            config[CONF_USERNAME], config[CONF_PASSWORD], "/tmp/vicare_token.save"
        )
    else:
        vicare_api = Device(
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            "/tmp/vicare_token.save",
            config[CONF_CIRCUIT],
        )
    add_entities([ViCareWater(f"{config[CONF_NAME]} Water", vicare_api)])


class ViCareWater(WaterHeaterDevice):
    """Representation of the ViCare domestic hot water device."""

    def __init__(self, name, api):
        """Initialize the DHW water_heater device."""
        self._name = name
        self._state = None
        self._api = api
        self._target_temperature = None
        self._current_temperature = None
        self._current_mode = None

    def update(self):
        """Let HA know there has been an update from the ViCare API."""
        current_temperature = self._api.getDomesticHotWaterStorageTemperature()
        if current_temperature is not None and current_temperature != "error":
            self._current_temperature = current_temperature
        else:
            self._current_temperature = -1

        self._target_temperature = self._api.getDomesticHotWaterConfiguredTemperature()

        self._current_mode = self._api.getActiveMode()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS_HEATER

    @property
    def name(self):
        """Return the name of the water_heater device."""
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
        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            self._target_temperature = temp
            self._api.setDomesticHotWaterTemperature(self._target_temperature)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return VICARE_TEMP_WATER_MIN

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return VICARE_TEMP_WATER_MAX

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return VICARE_TO_HA_HVAC_DHW.get(self._current_mode)

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        _LOGGER.error(
            "The DHW water_heater device does not support setting modes."
            "The current mode is only informative since. Setting it might conflict with the heating water_heater device"
        )

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return list(HA_TO_VICARE_HVAC_DHW.keys())
