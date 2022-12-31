"""Viessmann ViCare water_heater device."""
from contextlib import suppress
import logging
from typing import Any

from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_HEATING_TYPE,
    DOMAIN,
    VICARE_API,
    VICARE_DEVICE_CONFIG,
    VICARE_NAME,
)

_LOGGER = logging.getLogger(__name__)

VICARE_MODE_DHW = "dhw"
VICARE_MODE_HEATING = "heating"
VICARE_MODE_DHWANDHEATING = "dhwAndHeating"
VICARE_MODE_DHWANDHEATINGCOOLING = "dhwAndHeatingCooling"
VICARE_MODE_FORCEDREDUCED = "forcedReduced"
VICARE_MODE_FORCEDNORMAL = "forcedNormal"
VICARE_MODE_OFF = "standby"

VICARE_TEMP_WATER_MIN = 10
VICARE_TEMP_WATER_MAX = 60

OPERATION_MODE_ON = "on"
OPERATION_MODE_OFF = "off"

VICARE_TO_HA_HVAC_DHW = {
    VICARE_MODE_DHW: OPERATION_MODE_ON,
    VICARE_MODE_DHWANDHEATING: OPERATION_MODE_ON,
    VICARE_MODE_DHWANDHEATINGCOOLING: OPERATION_MODE_ON,
    VICARE_MODE_HEATING: OPERATION_MODE_OFF,
    VICARE_MODE_FORCEDREDUCED: OPERATION_MODE_OFF,
    VICARE_MODE_FORCEDNORMAL: OPERATION_MODE_ON,
    VICARE_MODE_OFF: OPERATION_MODE_OFF,
}

HA_TO_VICARE_HVAC_DHW = {
    OPERATION_MODE_OFF: VICARE_MODE_OFF,
    OPERATION_MODE_ON: VICARE_MODE_DHW,
}


def _get_circuits(vicare_api):
    """Return the list of circuits."""
    try:
        return vicare_api.circuits
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("No circuits found")
        return []


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ViCare climate platform."""
    name = VICARE_NAME
    entities = []
    api = hass.data[DOMAIN][config_entry.entry_id][VICARE_API]
    circuits = await hass.async_add_executor_job(_get_circuits, api)

    for circuit in circuits:
        suffix = ""
        if len(circuits) > 1:
            suffix = f" {circuit.id}"

        entity = ViCareWater(
            f"{name} Water{suffix}",
            api,
            circuit,
            hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG],
            config_entry.data[CONF_HEATING_TYPE],
        )
        entities.append(entity)

    async_add_entities(entities)


class ViCareWater(WaterHeaterEntity):
    """Representation of the ViCare domestic hot water device."""

    _attr_precision = PRECISION_TENTHS
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE

    def __init__(self, name, api, circuit, device_config, heating_type):
        """Initialize the DHW water_heater device."""
        self._name = name
        self._state = None
        self._api = api
        self._circuit = circuit
        self._device_config = device_config
        self._attributes = {}
        self._target_temperature = None
        self._current_temperature = None
        self._current_mode = None
        self._heating_type = heating_type

    def update(self) -> None:
        """Let HA know there has been an update from the ViCare API."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._current_temperature = (
                    self._api.getDomesticHotWaterStorageTemperature()
                )

            with suppress(PyViCareNotSupportedFeatureError):
                self._target_temperature = (
                    self._api.getDomesticHotWaterDesiredTemperature()
                )

            with suppress(PyViCareNotSupportedFeatureError):
                self._current_mode = self._circuit.getActiveMode()

        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)

    @property
    def unique_id(self) -> str:
        """Return unique ID for this device."""
        return f"{self._device_config.getConfig().serial}-{self._circuit.id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_config.getConfig().serial)},
            name=self._device_config.getModel(),
            manufacturer="Viessmann",
            model=self._device_config.getModel(),
            configuration_url="https://developer.viessmann.com/",
        )

    @property
    def name(self):
        """Return the name of the water_heater device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
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
    def target_temperature_step(self) -> float:
        """Set target temperature step to wholes."""
        return PRECISION_WHOLE

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return VICARE_TO_HA_HVAC_DHW.get(self._current_mode)

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return list(HA_TO_VICARE_HVAC_DHW)
