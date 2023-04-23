"""Support for particulate matter sensors connected to a serial port."""
from __future__ import annotations

import logging

from pmsensor import serial_pm as pm
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_BRAND = "brand"
CONF_SERIAL_DEVICE = "serial_device"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_BRAND): cv.string,
        vol.Required(CONF_SERIAL_DEVICE): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the available PM sensors."""
    try:
        coll = pm.PMDataCollector(
            config.get(CONF_SERIAL_DEVICE), pm.SUPPORTED_SENSORS[config.get(CONF_BRAND)]
        )
    except KeyError:
        _LOGGER.error(
            "Brand %s not supported\n supported brands: %s",
            config.get(CONF_BRAND),
            pm.SUPPORTED_SENSORS.keys(),
        )
        return
    except OSError as err:
        _LOGGER.error(
            "Could not open serial connection to %s (%s)",
            config.get(CONF_SERIAL_DEVICE),
            err,
        )
        return

    dev = []

    for pmname in coll.supported_values():
        if config.get(CONF_NAME) is not None:
            name = f"{config.get(CONF_NAME)} PM{pmname}"
        else:
            name = f"PM{pmname}"
        dev.append(ParticulateMatterSensor(coll, name, pmname))

    add_entities(dev)


class ParticulateMatterSensor(SensorEntity):
    """Representation of an Particulate matter sensor."""

    def __init__(self, pm_data_collector, name, pmname):
        """Initialize a new PM sensor."""
        self._name = name
        self._pmname = pmname
        self._state = None
        self._collector = pm_data_collector

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

    def update(self) -> None:
        """Read from sensor and update the state."""
        _LOGGER.debug("Reading data from PM sensor")
        try:
            self._state = self._collector.read_data()[self._pmname]
        except KeyError:
            _LOGGER.error("Could not read PM%s value", self._pmname)
