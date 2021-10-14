"""Viessmann ViCare sensor device."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import logging

from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_POWER,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from . import ViCareRequiredKeysMixin
from .const import DOMAIN, VICARE_API, VICARE_DEVICE_CONFIG, VICARE_NAME

_LOGGER = logging.getLogger(__name__)

SENSOR_CIRCULATION_PUMP_ACTIVE = "circulationpump_active"
SENSOR_BURNER_ACTIVE = "burner_active"
SENSOR_COMPRESSOR_ACTIVE = "compressor_active"


@dataclass
class ViCareBinarySensorEntityDescription(
    BinarySensorEntityDescription, ViCareRequiredKeysMixin
):
    """Describes ViCare binary sensor entity."""


CIRCUIT_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key=SENSOR_CIRCULATION_PUMP_ACTIVE,
        name="Circulation pump active",
        device_class=DEVICE_CLASS_POWER,
        value_getter=lambda api: api.getCirculationPumpActive(),
    ),
)

BURNER_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key=SENSOR_BURNER_ACTIVE,
        name="Burner active",
        device_class=DEVICE_CLASS_POWER,
        value_getter=lambda api: api.getActive(),
    ),
)

COMPRESSOR_SENSORS: tuple[ViCareBinarySensorEntityDescription, ...] = (
    ViCareBinarySensorEntityDescription(
        key=SENSOR_COMPRESSOR_ACTIVE,
        name="Compressor active",
        device_class=DEVICE_CLASS_POWER,
        value_getter=lambda api: api.getActive(),
    ),
)


def _build_entity(name, vicare_api, device_config, sensor):
    try:
        sensor.value_getter(vicare_api)
        _LOGGER.debug("Found entity %s", name)
        return ViCareBinarySensor(
            name,
            vicare_api,
            device_config,
            sensor,
        )
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("Feature not supported %s", name)
        return None
    except AttributeError:
        _LOGGER.debug("Attribute Error %s", name)
        return None


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Create the ViCare binary sensor devices."""
    if discovery_info is None:
        return

    name = hass.data[DOMAIN][VICARE_NAME]
    api = hass.data[DOMAIN][VICARE_API]

    all_devices = []

    for description in CIRCUIT_SENSORS:
        for circuit in api.circuits:
            suffix = ""
            if len(api.circuits) > 1:
                suffix = f" {circuit.id}"
            entity = await hass.async_add_executor_job(
                _build_entity,
                f"{name} {description.name}{suffix}",
                circuit,
                hass.data[DOMAIN][VICARE_DEVICE_CONFIG],
                description,
            )
            if entity is not None:
                all_devices.append(entity)

    try:
        for description in BURNER_SENSORS:
            for burner in api.burners:
                suffix = ""
                if len(api.burners) > 1:
                    suffix = f" {burner.id}"
                entity = await hass.async_add_executor_job(
                    _build_entity,
                    f"{name} {description.name}{suffix}",
                    burner,
                    hass.data[DOMAIN][VICARE_DEVICE_CONFIG],
                    description,
                )
                if entity is not None:
                    all_devices.append(entity)
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("No burners found")

    try:
        for description in COMPRESSOR_SENSORS:
            for compressor in api.compressors:
                suffix = ""
                if len(api.compressors) > 1:
                    suffix = f" {compressor.id}"
                entity = await hass.async_add_executor_job(
                    _build_entity,
                    f"{name} {description.name}{suffix}",
                    compressor,
                    hass.data[DOMAIN][VICARE_DEVICE_CONFIG],
                    description,
                )
                if entity is not None:
                    all_devices.append(entity)
    except PyViCareNotSupportedFeatureError:
        _LOGGER.info("No compressors found")

    async_add_entities(all_devices)


class ViCareBinarySensor(BinarySensorEntity):
    """Representation of a ViCare sensor."""

    entity_description: ViCareBinarySensorEntityDescription

    def __init__(
        self, name, api, device_config, description: ViCareBinarySensorEntityDescription
    ):
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_name = name
        self._api = api
        self.entity_description = description
        self._device_config = device_config
        self._state = None

    @property
    def device_info(self):
        """Return device info for this device."""
        return {
            "identifiers": {(DOMAIN, self._device_config.getConfig().serial)},
            "name": self._device_config.getModel(),
            "manufacturer": "Viessmann",
            "model": (DOMAIN, self._device_config.getModel()),
        }

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return f"{self._device_config.getConfig().serial}-{self._attr_name}"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update state of sensor."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._state = self.entity_description.value_getter(self._api)
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)
