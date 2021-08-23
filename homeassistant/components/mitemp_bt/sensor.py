"""Support for Xiaomi Mi Temp BLE environmental sensor."""
from __future__ import annotations

import logging
from typing import Any

import btlewrap
from btlewrap.base import BluetoothBackendException
from mitemp_bt import mitemp_bt_poller
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_FORCE_UPDATE,
    CONF_MAC,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_TIMEOUT,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv

try:
    import bluepy.btle  # noqa: F401 pylint: disable=unused-import

    BACKEND = btlewrap.BluepyBackend
except ImportError:
    BACKEND = btlewrap.GatttoolBackend

_LOGGER = logging.getLogger(__name__)

CONF_ADAPTER = "adapter"
CONF_CACHE = "cache_value"
CONF_MEDIAN = "median"
CONF_RETRIES = "retries"

DEFAULT_ADAPTER = "hci0"
DEFAULT_UPDATE_INTERVAL = 300
DEFAULT_FORCE_UPDATE = False
DEFAULT_MEDIAN = 3
DEFAULT_NAME = "MiTemp BT"
DEFAULT_RETRIES = 2
DEFAULT_TIMEOUT = 10


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=DEVICE_CLASS_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=DEVICE_CLASS_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
    ),
)

SENSOR_KEYS = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MEDIAN, default=DEFAULT_MEDIAN): cv.positive_int,
        vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_RETRIES, default=DEFAULT_RETRIES): cv.positive_int,
        vol.Optional(CONF_CACHE, default=DEFAULT_UPDATE_INTERVAL): cv.positive_int,
        vol.Optional(CONF_ADAPTER, default=DEFAULT_ADAPTER): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the MiTempBt sensor."""
    backend = BACKEND
    _LOGGER.debug("MiTempBt is using %s backend", backend.__name__)

    cache = config[CONF_CACHE]
    poller = mitemp_bt_poller.MiTempBtPoller(
        config[CONF_MAC],
        cache_timeout=cache,
        adapter=config[CONF_ADAPTER],
        backend=backend,
    )
    prefix = config[CONF_NAME]
    force_update = config[CONF_FORCE_UPDATE]
    median = config[CONF_MEDIAN]
    poller.ble_timeout = config[CONF_TIMEOUT]
    poller.retries = config[CONF_RETRIES]

    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    entities = [
        MiTempBtSensor(poller, prefix, force_update, median, description)
        for description in SENSOR_TYPES
        if description.key in monitored_conditions
    ]

    add_entities(entities)


class MiTempBtSensor(SensorEntity):
    """Implementing the MiTempBt sensor."""

    def __init__(
        self, poller, prefix, force_update, median, description: SensorEntityDescription
    ):
        """Initialize the sensor."""
        self.entity_description = description
        self.poller = poller
        self.data: list[Any] = []
        self._attr_name = f"{prefix} {description.name}"
        self._attr_force_update = force_update
        # Median is used to filter out outliers. median of 3 will filter
        # single outliers, while  median of 5 will filter double outliers
        # Use median_count = 1 if no filtering is required.
        self.median_count = median

    def update(self):
        """
        Update current conditions.

        This uses a rolling median over 3 values to filter out outliers.
        """
        try:
            _LOGGER.debug("Polling data for %s", self.name)
            data = self.poller.parameter_value(self.entity_description.key)
        except OSError as ioerr:
            _LOGGER.warning("Polling error %s", ioerr)
            return
        except BluetoothBackendException as bterror:
            _LOGGER.warning("Polling error %s", bterror)
            return

        if data is not None:
            _LOGGER.debug("%s = %s", self.name, data)
            self.data.append(data)
        else:
            _LOGGER.warning(
                "Did not receive any data from Mi Temp sensor %s", self.name
            )
            # Remove old data from median list or set sensor value to None
            # if no data is available anymore
            if self.data:
                self.data = self.data[1:]
            else:
                self._attr_native_value = None
            return

        if len(self.data) > self.median_count:
            self.data = self.data[1:]

        if len(self.data) == self.median_count:
            median = sorted(self.data)[int((self.median_count - 1) / 2)]
            _LOGGER.debug("Median is: %s", median)
            self._attr_native_value = median
        else:
            _LOGGER.debug("Not yet enough data for median calculation")
