"""Support for monitoring emoncms feeds."""
from __future__ import annotations

from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_URL,
    CONF_VALUE_TEMPLATE,
    STATE_UNKNOWN,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import template
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_FEEDID = "FeedId"
ATTR_FEEDNAME = "FeedName"
ATTR_LASTUPDATETIME = "LastUpdated"
ATTR_LASTUPDATETIMESTR = "LastUpdatedStr"
ATTR_SIZE = "Size"
ATTR_TAG = "Tag"
ATTR_USERID = "UserId"

CONF_EXCLUDE_FEEDID = "exclude_feed_id"
CONF_ONLY_INCLUDE_FEEDID = "include_only_feed_id"
CONF_SENSOR_NAMES = "sensor_names"

DECIMALS = 2
DEFAULT_UNIT = UnitOfPower.WATT
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

ONLY_INCL_EXCL_NONE = "only_include_exclude_or_none"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_ID): cv.positive_int,
        vol.Exclusive(CONF_ONLY_INCLUDE_FEEDID, ONLY_INCL_EXCL_NONE): vol.All(
            cv.ensure_list, [cv.positive_int]
        ),
        vol.Exclusive(CONF_EXCLUDE_FEEDID, ONLY_INCL_EXCL_NONE): vol.All(
            cv.ensure_list, [cv.positive_int]
        ),
        vol.Optional(CONF_SENSOR_NAMES): vol.All(
            {cv.positive_int: vol.All(cv.string, vol.Length(min=1))}
        ),
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=DEFAULT_UNIT): cv.string,
    }
)


def get_id(sensor: str, elem: dict[str, str]) -> str:
    """Return unique identifier for feed / sensor."""
    return f"emoncms{sensor}_{elem['tag']}_{elem['name']}_{elem['id']}_{elem['userid']}"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Emoncms sensor."""
    apikey = config.get(CONF_API_KEY)
    url = config.get(CONF_URL)
    sensorid = config.get(CONF_ID)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    config_unit = config.get(CONF_UNIT_OF_MEASUREMENT)
    exclude_feeds = config.get(CONF_EXCLUDE_FEEDID)
    include_only_feeds = config.get(CONF_ONLY_INCLUDE_FEEDID)
    sensor_names = config.get(CONF_SENSOR_NAMES)

    if value_template is not None:
        value_template.hass = hass

    data = EmonCmsData(url, apikey)

    data.update()

    if data.data is None:
        return

    sensors = []

    for elem in data.data:

        if exclude_feeds is not None and int(elem["id"]) in exclude_feeds:
            continue

        if include_only_feeds is not None and int(elem["id"]) not in include_only_feeds:
            continue

        name = None
        if sensor_names is not None:
            name = sensor_names.get(int(elem["id"]), None)

        if unit := elem.get("unit"):
            unit_of_measurement = unit
        else:
            unit_of_measurement = config_unit

        sensors.append(
            EmonCmsSensor(
                data,
                name,
                value_template,
                unit_of_measurement,
                str(sensorid),
                elem,
            )
        )
    add_entities(sensors)


class EmonCmsSensor(SensorEntity):
    """Implementation of an Emoncms sensor."""

    def __init__(self, data, name, value_template, unit_of_measurement, sensorid, elem):
        """Initialize the sensor."""
        if name is None:
            # Suppress ID in sensor name if it's 1, since most people won't
            # have more than one EmonCMS source and it's redundant to show the
            # ID if there's only one.
            id_for_name = "" if str(sensorid) == "1" else sensorid
            # Use the feed name assigned in EmonCMS or fall back to the feed ID
            feed_name = elem.get("name") or f"Feed {elem['id']}"
            self._attr_name = f"EmonCMS{id_for_name} {feed_name}"
        else:
            self._attr_name = name
        self._attr_unique_id = get_id(sensorid, elem)
        self._data = data
        self._value_template = value_template
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._sensorid = sensorid
        self._elem = elem

        if unit_of_measurement in ("kWh", "Wh"):
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif unit_of_measurement == "W":
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit_of_measurement == "V":
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit_of_measurement == "A":
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit_of_measurement == "VA":
            self._attr_device_class = SensorDeviceClass.APPARENT_POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit_of_measurement in ("°C", "°F", "K"):
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit_of_measurement == "Hz":
            self._attr_device_class = SensorDeviceClass.FREQUENCY
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit_of_measurement == "hPa":
            self._attr_device_class = SensorDeviceClass.PRESSURE
            self._attr_state_class = SensorStateClass.MEASUREMENT

        self._state = elem["value"]

    @property
    def native_value(self) -> str | float | None:
        """Render the state of the feed."""
        if self._value_template is not None:
            return self._value_template.render_with_possible_json_value(
                self._state, STATE_UNKNOWN
            )
        elif self._state is not None:
            return round(float(self._state), DECIMALS)
        else:
            return None

    @property
    def extra_state_attributes(self):
        """Return the attributes of the sensor."""
        return {
            ATTR_FEEDID: self._elem["id"],
            ATTR_TAG: self._elem["tag"],
            ATTR_FEEDNAME: self._elem["name"],
            ATTR_SIZE: self._elem["size"],
            ATTR_USERID: self._elem["userid"],
            ATTR_LASTUPDATETIME: self._elem["time"],
            ATTR_LASTUPDATETIMESTR: template.timestamp_local(float(self._elem["time"])),
        }

    def update(self) -> None:
        """Get the latest data and updates the state."""
        self._data.update()

        if self._data.data is None:
            return

        elem = next(
            (
                elem
                for elem in self._data.data
                if get_id(self._sensorid, elem) == self._attr_unique_id
            ),
            None,
        )

        if elem is None:
            return

        self._elem = elem
        self._state = elem["value"]


class EmonCmsData:
    """The class for handling the data retrieval."""

    def __init__(self, url, apikey):
        """Initialize the data object."""
        self._sess = requests.Session()
        self._sess.params = {"apikey": apikey}
        self._url = f"{url}/feed/list.json"
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Emoncms."""
        try:
            req = self._sess.get(self._url, allow_redirects=True, timeout=5)
            req.raise_for_status()
            self.data = req.json()
        except requests.exceptions.RequestException:
            _LOGGER.exception("Failed to get EmonCMS data")
