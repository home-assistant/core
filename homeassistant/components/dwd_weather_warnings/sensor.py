"""
Support for getting statistical data from a DWD Weather Warnings.

Data is fetched from DWD:
https://rcccm.dwd.de/DE/wetter/warnungen_aktuell/objekt_einbindung/objekteinbindung.html

Warnungen vor extremem Unwetter (Stufe 4)
Unwetterwarnungen (Stufe 3)
Warnungen vor markantem Wetter (Stufe 2)
Wetterwarnungen (Stufe 1)
"""
from datetime import timedelta
import logging

from dwdwfsapi import DwdWeatherWarningsAPI
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by DWD"

DEFAULT_NAME = "DWD-Weather-Warnings"

CONF_REGION_NAME = "region_name"

SCAN_INTERVAL = timedelta(minutes=15)

MONITORED_CONDITIONS = {
    "current_warning_level": [
        "Current Warning Level",
        None,
        "mdi:close-octagon-outline",
    ],
    "advance_warning_level": [
        "Advance Warning Level",
        None,
        "mdi:close-octagon-outline",
    ],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_REGION_NAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=list(MONITORED_CONDITIONS)
        ): vol.All(cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the DWD-Weather-Warnings sensor."""
    name = config.get(CONF_NAME)
    region_name = config.get(CONF_REGION_NAME)

    api = DwdWeatherWarningsAPI(region_name)

    # Build sensor list and activate update only for the first one
    sensors = []
    call_update = True
    for sensor_type in config[CONF_MONITORED_CONDITIONS]:
        sensors.append(DwdWeatherWarningsSensor(api, name, sensor_type, call_update))
        call_update = False

    add_entities(sensors, True)


class DwdWeatherWarningsSensor(Entity):
    """Representation of a DWD-Weather-Warnings sensor."""

    def __init__(self, api, name, sensor_type, call_update):
        """Initialize a DWD-Weather-Warnings sensor."""
        self._api = api
        self._name = name
        self._sensor_type = sensor_type
        self._call_update = call_update

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {MONITORED_CONDITIONS[self._sensor_type][0]}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return MONITORED_CONDITIONS[self._sensor_type][2]

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return MONITORED_CONDITIONS[self._sensor_type][1]

    @property
    def state(self):
        """Return the state of the device."""
        if self._sensor_type == "current_warning_level":
            warning_level = self._api.current_warning_level
        else:
            warning_level = self._api.expected_warning_level
        return warning_level

    @property
    def device_state_attributes(self):
        """Return the state attributes of the DWD-Weather-Warnings."""
        data = {ATTR_ATTRIBUTION: ATTRIBUTION}

        data["region_name"] = self._api.warncell_name
        data["region_id"] = self._api.warncell_id
        data["region_state"] = "N/A"  # Not available via new API
        if self._api.last_update is not None:
            data["last_update"] = dt_util.as_local(self._api.last_update)
        else:
            data["last_update"] = None

        if self._sensor_type == "current_warning_level":
            searched_warnings = self._api.current_warnings
        else:
            searched_warnings = self._api.expected_warnings

        data["warning_count"] = len(searched_warnings)
        i = 0
        for warning in searched_warnings:
            i = i + 1
            data[f"warning_{i}_name"] = warning["event"]
            data[f"warning_{i}_type"] = warning["event_code"]
            data[f"warning_{i}_level"] = warning["level"]
            data[f"warning_{i}_headline"] = warning["headline"]
            data[f"warning_{i}_description"] = warning["description"]
            data[f"warning_{i}_instruction"] = warning["instruction"]
            if warning["start_time"] is not None:
                data[f"warning_{i}_start"] = dt_util.as_local(warning["start_time"])
            else:
                data[f"warning_{i}_start"] = None
            if warning["end_time"] is not None:
                data[f"warning_{i}_end"] = dt_util.as_local(warning["end_time"])
            else:
                data[f"warning_{i}_end"] = None
            data[f"warning_{i}_parameters"] = warning["parameters"]
            data[f"warning_{i}_color"] = warning["color"]

            # Dictionary for the attribute containing the complete warning
            warning_copy = warning.copy()
            warning_copy["start_time"] = data[f"warning_{i}_start"]
            warning_copy["end_time"] = data[f"warning_{i}_end"]
            data[f"warning_{i}"] = warning_copy

        return data

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._api.data_valid

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from the DWD-Weather-Warnings API."""
        if self._call_update:
            self._api.update()
            _LOGGER.debug(
                "Update for %s (%s) by %s",
                self._api.warncell_name,
                self._api.warncell_id,
                self._sensor_type,
            )
