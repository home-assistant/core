"""Viessmann ViCare water_heater device."""
import logging

import requests

from homeassistant.components.water_heater import (
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterEntity,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, TEMP_CELSIUS

from . import DOMAIN as VICARE_DOMAIN, VICARE_API, VICARE_HEATING_TYPE, VICARE_NAME

_LOGGER = logging.getLogger(__name__)

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

PYVICARE_ERROR = "error"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the ViCare water_heater devices."""
    if discovery_info is None:
        return
    vicare_api = hass.data[VICARE_DOMAIN][VICARE_API]
    heating_type = hass.data[VICARE_DOMAIN][VICARE_HEATING_TYPE]
    add_entities(
        [
            ViCareWater(
                f"{hass.data[VICARE_DOMAIN][VICARE_NAME]} Water",
                vicare_api,
                heating_type,
            )
        ]
    )


class ViCareWater(WaterHeaterEntity):
    """Representation of the ViCare domestic hot water device."""

    def __init__(self, name, api, heating_type):
        """Initialize the DHW water_heater device."""
        self._name = name
        self._state = None
        self._api = api
        self._attributes = {}
        self._target_temperature = None
        self._current_temperature = None
        self._current_mode = None
        self._heating_type = heating_type

    def update(self):
        """Let HA know there has been an update from the ViCare API."""
        try:
            current_temperature = self._api.getDomesticHotWaterStorageTemperature()
            if current_temperature != PYVICARE_ERROR:
                self._current_temperature = current_temperature
            else:
                self._current_temperature = None

            self._target_temperature = (
                self._api.getDomesticHotWaterConfiguredTemperature()
            )

            self._current_mode = self._api.getActiveMode()
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")

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
            self._api.setDomesticHotWaterTemperature(temp)
            self._target_temperature = temp

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

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return list(HA_TO_VICARE_HVAC_DHW)
