"""Viessmann ViCare sensor device."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import logging
from typing import Union

from PyViCare.PyViCare import PyViCareNotSupportedFeatureError, PyViCareRateLimitError
from PyViCare.PyViCareDevice import Device
from PyViCare.PyViCareGazBoiler import GazBoiler
from PyViCare.PyViCareHeatPump import HeatPump
import requests

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_POWER,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from . import (
    DOMAIN as VICARE_DOMAIN,
    VICARE_API,
    VICARE_HEATING_TYPE,
    VICARE_NAME,
    ApiT,
    HeatingType,
    ViCareRequiredKeysMixin,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_CIRCULATION_PUMP_ACTIVE = "circulationpump_active"

# gas sensors
SENSOR_BURNER_ACTIVE = "burner_active"

# heatpump sensors
SENSOR_COMPRESSOR_ACTIVE = "compressor_active"


@dataclass
class ViCareBinarySensorEntityDescription(
    BinarySensorEntityDescription, ViCareRequiredKeysMixin[ApiT]
):
    """Describes ViCare binary sensor entity."""


SENSOR_TYPES_GENERIC: tuple[ViCareBinarySensorEntityDescription[Device]] = (
    ViCareBinarySensorEntityDescription[Device](
        key=SENSOR_CIRCULATION_PUMP_ACTIVE,
        name="Circulation pump active",
        device_class=DEVICE_CLASS_POWER,
        value_getter=lambda api: api.getCirculationPumpActive(),
    ),
)

SENSOR_TYPES_GAS: tuple[ViCareBinarySensorEntityDescription[GazBoiler]] = (
    ViCareBinarySensorEntityDescription[GazBoiler](
        key=SENSOR_BURNER_ACTIVE,
        name="Burner active",
        device_class=DEVICE_CLASS_POWER,
        value_getter=lambda api: api.getBurnerActive(),
    ),
)

SENSOR_TYPES_HEATPUMP: tuple[ViCareBinarySensorEntityDescription[HeatPump]] = (
    ViCareBinarySensorEntityDescription[HeatPump](
        key=SENSOR_COMPRESSOR_ACTIVE,
        name="Compressor active",
        device_class=DEVICE_CLASS_POWER,
        value_getter=lambda api: api.getCompressorActive(),
    ),
)

SENSORS_GENERIC = [SENSOR_CIRCULATION_PUMP_ACTIVE]

SENSORS_BY_HEATINGTYPE = {
    HeatingType.gas: [SENSOR_BURNER_ACTIVE],
    HeatingType.heatpump: [SENSOR_COMPRESSOR_ACTIVE],
    HeatingType.fuelcell: [SENSOR_BURNER_ACTIVE],
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the ViCare sensor devices."""
    if discovery_info is None:
        return

    vicare_api = hass.data[VICARE_DOMAIN][VICARE_API]
    heating_type = hass.data[VICARE_DOMAIN][VICARE_HEATING_TYPE]

    sensors = SENSORS_GENERIC.copy()

    if heating_type != HeatingType.generic:
        sensors.extend(SENSORS_BY_HEATINGTYPE[heating_type])

    add_entities(
        [
            ViCareBinarySensor(
                hass.data[VICARE_DOMAIN][VICARE_NAME], vicare_api, description
            )
            for description in (
                *SENSOR_TYPES_GENERIC,
                *SENSOR_TYPES_GAS,
                *SENSOR_TYPES_HEATPUMP,
            )
            if description.key in sensors
        ]
    )


DescriptionT = Union[
    ViCareBinarySensorEntityDescription[Device],
    ViCareBinarySensorEntityDescription[GazBoiler],
    ViCareBinarySensorEntityDescription[HeatPump],
]


class ViCareBinarySensor(BinarySensorEntity):
    """Representation of a ViCare sensor."""

    entity_description: DescriptionT

    def __init__(self, name, api, description: DescriptionT):
        """Initialize the sensor."""
        self._attr_name = f"{name} {description.name}"
        self._api = api
        self._state = None

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._api.service.id}-{self.entity_description.key}"

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
