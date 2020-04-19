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
import json
import logging

import voluptuous as vol

from homeassistant.components.rest.sensor import RestData
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE as HA_USER_AGENT
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
        vol.Optional(CONF_REGION_NAME): cv.string,
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

    sensors = [
        DwdWeatherWarningsSensor(api, name, condition)
        for condition in config[CONF_MONITORED_CONDITIONS]
    ]

    add_entities(sensors, True)


class DwdWeatherWarningsSensor(Entity):
    """Representation of a DWD-Weather-Warnings sensor."""

    def __init__(self, api, name, variable):
        """Initialize a DWD-Weather-Warnings sensor."""
        self._api = api
        self._name = name
        self._var_id = variable

        variable_info = MONITORED_CONDITIONS[variable]
        self._var_name = variable_info[0]
        self._var_units = variable_info[1]
        self._var_icon = variable_info[2]

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._var_name}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._var_icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._var_units

    @property
    def state(self):
        """Return the state of the device."""
        try:
            return round(self._api.data[self._var_id], 2)
        except TypeError:
            return self._api.data[self._var_id]

    @property
    def device_state_attributes(self):
        """Return the state attributes of the DWD-Weather-Warnings."""
        data = {ATTR_ATTRIBUTION: ATTRIBUTION, "region_name": self._api.region_name}

        if self._api.region_id is not None:
            data["region_id"] = self._api.region_id

        if self._api.region_state is not None:
            data["region_state"] = self._api.region_state

        if self._api.data["time"] is not None:
            data["last_update"] = dt_util.as_local(
                dt_util.utc_from_timestamp(self._api.data["time"] / 1000)
            )

        if self._var_id == "current_warning_level":
            prefix = "current"
        elif self._var_id == "advance_warning_level":
            prefix = "advance"
        else:
            raise Exception("Unknown warning type")

        data["warning_count"] = self._api.data[f"{prefix}_warning_count"]
        i = 0
        for event in self._api.data[f"{prefix}_warnings"]:
            i = i + 1

            # dictionary for the attribute containing the complete warning as json
            event_json = event.copy()

            data[f"warning_{i}_name"] = event["event"]
            data[f"warning_{i}_level"] = event["level"]
            data[f"warning_{i}_type"] = event["type"]
            if event["headline"]:
                data[f"warning_{i}_headline"] = event["headline"]
            if event["description"]:
                data[f"warning_{i}_description"] = event["description"]
            if event["instruction"]:
                data[f"warning_{i}_instruction"] = event["instruction"]

            if event["start"] is not None:
                data[f"warning_{i}_start"] = dt_util.as_local(
                    dt_util.utc_from_timestamp(event["start"] / 1000)
                )
                event_json["start"] = data[f"warning_{i}_start"]

            if event["end"] is not None:
                data[f"warning_{i}_end"] = dt_util.as_local(
                    dt_util.utc_from_timestamp(event["end"] / 1000)
                )
                event_json["end"] = data[f"warning_{i}_end"]

            data[f"warning_{i}"] = event_json

        return data

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._api.available

    def update(self):
        """Get the latest data from the DWD-Weather-Warnings API."""
        self._api.update()


class DwdWeatherWarningsAPI:
    """Get the latest data and update the states."""

    def __init__(self, region_name):
        """Initialize the data object."""
        resource = "https://www.dwd.de/DWD/warnungen/warnapp_landkreise/json/warnings.json?jsonp=loadWarnings"

        # a User-Agent is necessary for this rest api endpoint (#29496)
        headers = {"User-Agent": HA_USER_AGENT}

        self._rest = RestData("GET", resource, None, headers, None, True)
        self.region_name = region_name
        self.region_id = None
        self.region_state = None
        self.data = None
        self.available = True
        self.update()

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from the DWD-Weather-Warnings."""
        try:
            self._rest.update()

            json_string = self._rest.data[24 : len(self._rest.data) - 2]
            json_obj = json.loads(json_string)

            data = {"time": json_obj["time"]}

            for mykey, myvalue in {
                "current": "warnings",
                "advance": "vorabInformation",
            }.items():

                _LOGGER.debug(
                    "Found %d %s global DWD warnings", len(json_obj[myvalue]), mykey
                )

                data[f"{mykey}_warning_level"] = 0
                my_warnings = []

                if self.region_id is not None:
                    # get a specific region_id
                    if self.region_id in json_obj[myvalue]:
                        my_warnings = json_obj[myvalue][self.region_id]

                else:
                    # loop through all items to find warnings, region_id
                    # and region_state for region_name
                    for key in json_obj[myvalue]:
                        my_region = json_obj[myvalue][key][0]["regionName"]
                        if my_region != self.region_name:
                            continue
                        my_warnings = json_obj[myvalue][key]
                        my_state = json_obj[myvalue][key][0]["stateShort"]
                        self.region_id = key
                        self.region_state = my_state
                        break

                # Get max warning level
                maxlevel = data[f"{mykey}_warning_level"]
                for event in my_warnings:
                    if event["level"] >= maxlevel:
                        data[f"{mykey}_warning_level"] = event["level"]

                data[f"{mykey}_warning_count"] = len(my_warnings)
                data[f"{mykey}_warnings"] = my_warnings

                _LOGGER.debug("Found %d %s local DWD warnings", len(my_warnings), mykey)

            self.data = data
            self.available = True
        except TypeError:
            _LOGGER.error("Unable to fetch data from DWD-Weather-Warnings")
            self.available = False
