"""Sensor platform for Open Hardware Monitor."""

from __future__ import annotations

from datetime import timedelta
import functools
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
from homeassistant.util.dt import utcnow

_LOGGER = logging.getLogger(__name__)

STATE_MIN_VALUE = "minimal_value"
STATE_MAX_VALUE = "maximum_value"
STATE_VALUE = "value"
STATE_OBJECT = "object"
CONF_INTERVAL = "interval"
CONF_POLLING_ENABLED = "polling_enabled"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)
SCAN_INTERVAL = timedelta(seconds=30)
RETRY_INTERVAL = timedelta(seconds=30)

OHM_VALUE = "Value"
OHM_MIN = "Min"
OHM_MAX = "Max"
OHM_CHILDREN = "Children"
OHM_NAME = "Text"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=8085): cv.port,
        vol.Optional(CONF_POLLING_ENABLED, default=True): cv.boolean,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Open Hardware Monitor sensors from a config entry."""
    config = {
        CONF_HOST: entry.data[CONF_HOST],
        CONF_PORT: entry.data.get(CONF_PORT, 8085),
        CONF_POLLING_ENABLED: entry.data.get(CONF_POLLING_ENABLED, True),
    }
    data = OpenHardwareMonitorData(config, hass)
    # Run the blocking initialize in the executor to avoid blocking the event loop
    await hass.async_add_executor_job(functools.partial(data.initialize, utcnow()))
    async_add_entities(data.devices)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Open Hardware Monitor platform."""
    polling_enabled = config.get(CONF_POLLING_ENABLED, True)
    data = OpenHardwareMonitorData(config, hass)
    if data.data is None:
        raise PlatformNotReady
    entities = data.devices
    if not polling_enabled:
        for entity in entities:
            entity.should_poll = False
    add_entities(entities, True)


class OpenHardwareMonitorDevice(SensorEntity):
    """Device used to display information from OpenHardwareMonitor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = True

    def __init__(self, data, name, path, unit_of_measurement):
        """Initialize an OpenHardwareMonitor sensor."""
        self._name = name
        self._data = data
        self.path = path
        self.attributes = {}
        self._unit_of_measurement = unit_of_measurement
        self.value = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def native_value(self):
        """Return the state of the device."""
        if self.value == "-":
            return None
        return self.value

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the entity."""
        return self.attributes

    @classmethod
    def parse_number(cls, string):
        """In some locales a decimal numbers uses ',' instead of '.'."""
        return string.replace(",", ".")

    async def async_update(self) -> None:
        """Update the device from a new JSON object."""
        # Run the blocking update in the executor to avoid blocking the event loop
        await self._data.hass.async_add_executor_job(self._data.update)

        array = self._data.data[OHM_CHILDREN]
        _attributes = {}

        for path_index, path_number in enumerate(self.path):
            values = array[path_number]

            if path_index == len(self.path) - 1:
                self.value = self.parse_number(values[OHM_VALUE].split(" ")[0])
                _attributes.update(
                    {
                        "name": values[OHM_NAME],
                        STATE_MIN_VALUE: self.parse_number(
                            values[OHM_MIN].split(" ")[0]
                        ),
                        STATE_MAX_VALUE: self.parse_number(
                            values[OHM_MAX].split(" ")[0]
                        ),
                    }
                )

                self.attributes = _attributes
                return
            array = array[path_number][OHM_CHILDREN]
            _attributes.update({f"level_{path_index}": values[OHM_NAME]})


class OpenHardwareMonitorData:
    """Class used to pull data from OHM and create sensors."""

    def __init__(self, config, hass):
        """Initialize the Open Hardware Monitor data-handler."""
        self.data = None
        self._config = config
        self.hass = hass
        self.devices = []
        # Do not call initialize here, as it may block the event loop

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Hit by the timer with the configured interval."""
        if self.data is None:
            self.initialize(utcnow())
        else:
            self.refresh()

    def refresh(self):
        """Download and parse JSON from OHM."""
        data_url = (
            f"http://{self._config.get(CONF_HOST)}:"
            f"{self._config.get(CONF_PORT)}/data.json"
        )

        try:
            response = requests.get(data_url, timeout=30)
            self.data = response.json()
        except requests.exceptions.ConnectionError:
            _LOGGER.debug("ConnectionError: Is OpenHardwareMonitor running?")

    def initialize(self, now):
        """Parse of the sensors and adding of devices."""
        self.refresh()

        if self.data is None:
            return

        self.devices = self.parse_children(self.data, [], [], [])

    def parse_children(self, json, devices, path, names):
        """Recursively loop through child objects, finding the values."""
        result = devices.copy()

        if json[OHM_CHILDREN]:
            for child_index in range(len(json[OHM_CHILDREN])):
                child_path = path.copy()
                child_path.append(child_index)

                child_names = names.copy()
                if path:
                    child_names.append(json[OHM_NAME])

                obj = json[OHM_CHILDREN][child_index]

                added_devices = self.parse_children(
                    obj, devices, child_path, child_names
                )

                result = result + added_devices
            return result

        if json[OHM_VALUE].find(" ") == -1:
            return result

        unit_of_measurement = json[OHM_VALUE].split(" ")[1]
        child_names = names.copy()
        child_names.append(json[OHM_NAME])
        fullname = " ".join(child_names)

        dev = OpenHardwareMonitorDevice(self, fullname, path, unit_of_measurement)

        result.append(dev)
        return result
