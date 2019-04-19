"""
Support for getting statistical data from a DWD Weather Warnings.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dwd_weather_warnings/

Data is fetched from DWD using WFS 2.0 services
https://www.dwd.de/DE/leistungen/opendata/help/warnungen/cap_dwd_profile_de_pdf.pdf?__blob=publicationFile&v=7

Warnungen vor extremem Unwetter (Stufe 4)
Unwetterwarnungen (Stufe 3)
Warnungen vor markantem Wetter (Stufe 2)
Wetterwarnungen (Stufe 1)
"""

import logging
import json
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_NAME, CONF_MONITORED_CONDITIONS)
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util
from homeassistant.components.rest.sensor import RestData

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by DWD"

DEFAULT_NAME = 'DWD-Weather-Warnings'

CONF_REGION_NAME = 'region_name'

SCAN_INTERVAL = timedelta(minutes=15)

MONITORED_CONDITIONS = {
    'current_warning_level': ['Current Warning Level',
                              None, 'mdi:close-octagon-outline'],
    'advance_warning_level': ['Advance Warning Level',
                              None, 'mdi:close-octagon-outline'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_REGION_NAME): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS,
                 default=list(MONITORED_CONDITIONS)):
    vol.All(cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the DWD-Weather-Warnings sensor."""
    name = config.get(CONF_NAME)
    region_name = config.get(CONF_REGION_NAME)

    api = DwdWeatherWarningsAPI(region_name)

    sensors = [DwdWeatherWarningsSensor(api, name, condition)
               for condition in config[CONF_MONITORED_CONDITIONS]]

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
        return "{} {}".format(self._name, self._var_name)

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
        data = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            'region_name': self._api.region_name
        }

        if self._api.region_id is not None:
            data['region_id'] = self._api.region_id

        if self._api.data is not None:
            data['last_update'] = dt_util.as_local(
                dt_util.parse_datetime(self._api.data['timeStamp']))

        if self._var_id == 'current_warning_level':
            prefix = 'current'
        elif self._var_id == 'advance_warning_level':
            prefix = 'advance'
        else:
            raise Exception('Unknown warning type')

        data['warning_count'] = self._api.data[prefix + '_warning_count']
        i = 0
        for event in self._api.data[prefix + '_warnings']:
            i = i + 1

            data['warning_{}_name'.format(i)] = event['EVENT']
            data['warning_{}_level'.format(i)] = \
                self._api.warning_category_dict[event["SEVERITY"]]

            if event['HEADLINE']:
                data['warning_{}_headline'.format(i)] = event['HEADLINE']
            if event['DESCRIPTION']:
                data['warning_{}_description'.format(i)] = event['DESCRIPTION']
            if event['INSTRUCTION']:
                data['warning_{}_instruction'.format(i)] = event['INSTRUCTION']
            if event['CERTAINTY']:
                data['warning_{}_certainty'.format(i)] = event['CERTAINTY']
            if event['PARAMETERNAME']:
                data['warning_{}_{}'.format(i, event['PARAMETERNAME'])] = \
                    event['PARAMETERVALUE']
            if event['EFFECTIVE']:
                data['warning_{}_start'.format(i)] = event["EFFECTIVE"]
            if event['EXPIRES']:
                data['warning_{}_end'.format(i)] = event["EXPIRES"]

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

    warning_category_dict = {
        "Minor": 1,
        "Moderate": 2,
        "Severe": 3,
        "Extreme": 4
    }

    def __init__(self, region_name):
        """Initialize the data object."""
        self.region_name = region_name

        if not self.region_name:
            _LOGGER.error('No region configured!')
            self.available = False
            return

        if not self.regioncheck():
            return

        resource = "{}{}{}{}{}{}{}".format(
            'https://',
            'maps.dwd.de',
            '/geoserver/dwd/',
            'ows?service=WFS&version=2.0.0&request=GetFeature&typeName=',
            'dwd:Warnungen_Landkreise&CQL_FILTER=GC_WARNCELLID=%27',
            self.region_id,
            '%27&OutputFormat=application/json',
        )

        self._rest = RestData('GET', resource, None, None, None, True)

        self.region_id = None
        self.data = None
        self.available = True
        self.update()

    def regioncheck(self):
        """Check if the region exists and get warncell id."""
        regioncheck_resource = "{}{}{}{}{}{}{}".format(
            'https://',
            'maps.dwd.de',
            '/geoserver/dwd/',
            'ows?service=WFS&version=2.0.0&request=GetFeature&typeName=',
            'dwd:Warngebiete_Kreise&CQL_FILTER=NAME=%27',
            self.region_name,
            '%27&OutputFormat=application/json',
        )

        regioncheck_rest = RestData('GET', regioncheck_resource,
                                    None, None, None, True)
        regioncheck_rest.update()

        json_obj = json.loads(regioncheck_rest.data)

        if not json_obj["numberReturned"]:
            _LOGGER.error('Configured region %s is not known!',
                          self.region_name)
            self.available = False
            return False

        self.region_id = json_obj["features"][0]["properties"]["WARNCELLID"]

        return True

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from the DWD-Weather-Warnings."""
        if not self.available:
            return
        try:
            self._rest.update()

            json_obj = json.loads(self._rest.data)

            data = {"timeStamp": json_obj["timeStamp"]}

            immediate_maxlevel = 0
            future_maxlevel = 0
            immediate_warnings = []
            future_warnings = []

            if json_obj["numberReturned"]:

                for feature in json_obj["features"]:
                    warning = feature["properties"]

                    if warning["URGENCY"] == "Immediate":
                        immediate_warnings.append(warning)
                        immediate_maxlevel = max(self.warning_category_dict[
                            warning["SEVERITY"]],
                                                 immediate_maxlevel)
                    # Future warnings
                    else:
                        future_warnings.append(warning)
                        future_maxlevel = max(self.warning_category_dict[
                            warning["SEVERITY"]],
                                              future_maxlevel)

            data['current_warning_level'] = immediate_maxlevel
            data['current_warning_count'] = len(immediate_warnings)
            data['current_warnings'] = immediate_warnings

            data['advance_warning_level'] = future_maxlevel
            data['advance_warning_count'] = len(future_warnings)
            data['advance_warnings'] = future_warnings

            self.data = data
            self.available = True

        except TypeError:
            _LOGGER.error("Unable to fetch data from DWD-Weather-Warnings")
            self.available = False
