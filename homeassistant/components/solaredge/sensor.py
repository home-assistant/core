"""
Support for SolarEdge Monitoring API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.solaredge/
"""

from datetime import timedelta
import logging

import voluptuous as vol

from requests.exceptions import HTTPError, ConnectTimeout
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_MONITORED_CONDITIONS, CONF_NAME, POWER_WATT,
    ENERGY_WATT_HOUR)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['solaredge==0.0.2', 'stringcase==1.2.0']

# Config for solaredge monitoring api requests.
CONF_SITE_ID = "site_id"

OVERVIEW_UPDATE_DELAY = timedelta(minutes=10)
DETAILS_UPDATE_DELAY = timedelta(hours=12)
INVENTORY_UPDATE_DELAY = timedelta(hours=12)
POWER_FLOW_UPDATE_DELAY = timedelta(minutes=10)

SCAN_INTERVAL = timedelta(minutes=10)

# Supported overview sensor types:
# Key: ['json_key', 'name', unit, icon]
SENSOR_TYPES = {
    'lifetime_energy': ['lifeTimeData', "Lifetime energy",
                        ENERGY_WATT_HOUR, 'mdi:solar-power'],
    'energy_this_year': ['lastYearData', "Energy this year",
                         ENERGY_WATT_HOUR, 'mdi:solar-power'],
    'energy_this_month': ['lastMonthData', "Energy this month",
                          ENERGY_WATT_HOUR, 'mdi:solar-power'],
    'energy_today': ['lastDayData', "Energy today",
                     ENERGY_WATT_HOUR, 'mdi:solar-power'],
    'current_power': ['currentPower', "Current Power", POWER_WATT,
                      'mdi:solar-power'],
    'site_details': [None, 'Site details', None, None],
    'meters': ['meters', 'Meters', None, None],
    'sensors': ['sensors', 'Sensors', None, None],
    'gateways': ['gateways', 'Gateways', None, None],
    'batteries': ['batteries', 'Batteries', None, None],
    'inverters': ['inverters', 'Inverters', None, None],
    'power_consumption': ['LOAD', 'Power Consumption', None, 'mdi:flash'],
    'solar_power': ['PV', 'Solar Power', None, 'mdi:solar-power'],
    'grid_power': ['GRID', 'Grid Power', None, 'mdi:power-plug'],
    'storage_power': ['STORAGE', 'Storage Power', None, 'mdi:car-battery']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_SITE_ID): cv.string,
    vol.Optional(CONF_NAME, default='SolarEdge'): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=['current_power']):
    vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)])
})

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the SolarEdge Monitoring API sensor."""
    import solaredge

    api_key = config[CONF_API_KEY]
    site_id = config[CONF_SITE_ID]
    platform_name = config[CONF_NAME]

    # Create new SolarEdge object to retrieve data
    api = solaredge.Solaredge(api_key)

    # Check if api can be reached and site is active
    try:
        response = api.get_details(site_id)

        if response['details']['status'].lower() != 'active':
            _LOGGER.error("SolarEdge site is not active")
            return
        _LOGGER.debug("Credentials correct and site is active")
    except KeyError:
        _LOGGER.error("Missing details data in solaredge response")
        return
    except (ConnectTimeout, HTTPError):
        _LOGGER.error("Could not retrieve details from SolarEdge API")
        return

    # Create sensor factory that will create sensors based on sensor_key.
    sensor_factory = SolarEdgeSensorFactory(platform_name, site_id, api)

    # Create a new sensor for each sensor type.
    entities = []
    for sensor_key in config[CONF_MONITORED_CONDITIONS]:
        sensor = sensor_factory.create_sensor(sensor_key)
        if sensor is not None:
            entities.append(sensor)

    add_entities(entities, True)


class SolarEdgeSensorFactory:
    """Factory which creates sensors based on the sensor_key."""

    def __init__(self, platform_name, site_id, api):
        """Initialize the factory."""
        self.platform_name = platform_name

        details = SolarEdgeDetailsDataService(api, site_id)
        overview = SolarEdgeOverviewDataService(api, site_id)
        inventory = SolarEdgeInventoryDataService(api, site_id)
        flow = SolarEdgePowerFlowDataService(api, site_id)

        self.services = {
            'site_details': (SolarEdgeDetailsSensor, details)
        }

        for key in ['lifetime_energy', 'energy_this_year', 'energy_this_month',
                    'energy_today', 'current_power']:
            self.services[key] = (SolarEdgeOverviewSensor, overview)

        for key in ['meters', 'sensors', 'gateways', 'batteries', 'inverters']:
            self.services[key] = (SolarEdgeInventorySensor, inventory)

        for key in ['power_consumption', 'solar_power', 'grid_power',
                    'storage_power']:
            self.services[key] = (SolarEdgePowerFlowSensor, flow)

    def create_sensor(self, sensor_key):
        """Create and return a sensor based on the sensor_key."""
        sensor_class, service = self.services[sensor_key]

        return sensor_class(self.platform_name, sensor_key, service)


class SolarEdgeSensor(Entity):
    """Abstract class for a solaredge sensor."""

    def __init__(self, platform_name, sensor_key, data_service):
        """Initialize the sensor."""
        self.platform_name = platform_name
        self.sensor_key = sensor_key
        self.data_service = data_service

        self._state = None

        self._unit_of_measurement = SENSOR_TYPES[self.sensor_key][2]
        self._icon = SENSOR_TYPES[self.sensor_key][3]

    @property
    def name(self):
        """Return the name."""
        return "{} ({})".format(self.platform_name,
                                SENSOR_TYPES[self.sensor_key][1])

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the sensor icon."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state


class SolarEdgeOverviewSensor(SolarEdgeSensor):
    """Representation of an SolarEdge Monitoring API overview sensor."""

    def __init__(self, platform_name, sensor_key, data_service):
        """Initialize the overview sensor."""
        super().__init__(platform_name, sensor_key, data_service)

        self._json_key = SENSOR_TYPES[self.sensor_key][0]

    def update(self):
        """Get the latest data from the sensor and update the state."""
        self.data_service.update()
        self._state = self.data_service.data[self._json_key]


class SolarEdgeDetailsSensor(SolarEdgeSensor):
    """Representation of an SolarEdge Monitoring API details sensor."""

    def __init__(self, platform_name, sensor_key, data_service):
        """Initialize the details sensor."""
        super().__init__(platform_name, sensor_key, data_service)

        self._attributes = {}

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def update(self):
        """Get the latest details and update state and attributes."""
        self.data_service.update()
        self._state = self.data_service.data
        self._attributes = self.data_service.attributes


class SolarEdgeInventorySensor(SolarEdgeSensor):
    """Representation of an SolarEdge Monitoring API inventory sensor."""

    def __init__(self, platform_name, sensor_key, data_service):
        """Initialize the inventory sensor."""
        super().__init__(platform_name, sensor_key, data_service)

        self._json_key = SENSOR_TYPES[self.sensor_key][0]

        self._attributes = {}

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def update(self):
        """Get the latest inventory data and update state and attributes."""
        self.data_service.update()
        self._state = self.data_service.data[self._json_key]
        self._attributes = self.data_service.attributes[self._json_key]


class SolarEdgePowerFlowSensor(SolarEdgeSensor):
    """Representation of an SolarEdge Monitoring API power flow sensor."""

    def __init__(self, platform_name, sensor_key, data_service):
        """Initialize the power flow sensor."""
        super().__init__(platform_name, sensor_key, data_service)

        self._json_key = SENSOR_TYPES[self.sensor_key][0]

        self._attributes = {}

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def update(self):
        """Get the latest inventory data and update state and attributes."""
        self.data_service.update()
        self._state = self.data_service.data.get(self._json_key)
        self._attributes = self.data_service.attributes.get(self._json_key)
        self._unit_of_measurement = self.data_service.unit


class SolarEdgeDataService:
    """Get and update the latest data."""

    def __init__(self, api, site_id):
        """Initialize the data object."""
        self.api = api
        self.site_id = site_id

        self.data = {}
        self.attributes = {}


class SolarEdgeOverviewDataService(SolarEdgeDataService):
    """Get and update the latest overview data."""

    @Throttle(OVERVIEW_UPDATE_DELAY)
    def update(self):
        """Update the data from the SolarEdge Monitoring API."""
        try:
            data = self.api.get_overview(self.site_id)
            overview = data['overview']
        except KeyError:
            _LOGGER.error("Missing overview data, skipping update")
            return
        except (ConnectTimeout, HTTPError):
            _LOGGER.error("Could not retrieve data, skipping update")
            return

        self.data = {}

        for key, value in overview.items():
            if key in ['lifeTimeData', 'lastYearData',
                       'lastMonthData', 'lastDayData']:
                data = value['energy']
            elif key in ['currentPower']:
                data = value['power']
            else:
                data = value
            self.data[key] = data

        _LOGGER.debug("Updated SolarEdge overview: %s", self.data)


class SolarEdgeDetailsDataService(SolarEdgeDataService):
    """Get and update the latest details data."""

    def __init__(self, api, site_id):
        """Initialize the details data service."""
        super().__init__(api, site_id)

        self.data = None

    @Throttle(DETAILS_UPDATE_DELAY)
    def update(self):
        """Update the data from the SolarEdge Monitoring API."""
        from stringcase import snakecase

        try:
            data = self.api.get_details(self.site_id)
            details = data['details']
        except KeyError:
            _LOGGER.error("Missing details data, skipping update")
            return
        except (ConnectTimeout, HTTPError):
            _LOGGER.error("Could not retrieve data, skipping update")
            return

        self.data = None
        self.attributes = {}

        for key, value in details.items():
            key = snakecase(key)

            if key in ['primary_module']:
                for module_key, module_value in value.items():
                    self.attributes[snakecase(module_key)] = module_value
            elif key in ['peak_power', 'type', 'name', 'last_update_time',
                         'installation_date']:
                self.attributes[key] = value
            elif key == 'status':
                self.data = value

        _LOGGER.debug("Updated SolarEdge details: %s, %s",
                      self.data, self.attributes)


class SolarEdgeInventoryDataService(SolarEdgeDataService):
    """Get and update the latest inventory data."""

    @Throttle(INVENTORY_UPDATE_DELAY)
    def update(self):
        """Update the data from the SolarEdge Monitoring API."""
        try:
            data = self.api.get_inventory(self.site_id)
            inventory = data['Inventory']
        except KeyError:
            _LOGGER.error("Missing inventory data, skipping update")
            return
        except (ConnectTimeout, HTTPError):
            _LOGGER.error("Could not retrieve data, skipping update")
            return

        self.data = {}
        self.attributes = {}

        for key, value in inventory.items():
            self.data[key] = len(value)
            self.attributes[key] = {key: value}

        _LOGGER.debug("Updated SolarEdge inventory: %s, %s",
                      self.data, self.attributes)


class SolarEdgePowerFlowDataService(SolarEdgeDataService):
    """Get and update the latest power flow data."""

    def __init__(self, api, site_id):
        """Initialize the power flow data service."""
        super().__init__(api, site_id)

        self.unit = None

    @Throttle(POWER_FLOW_UPDATE_DELAY)
    def update(self):
        """Update the data from the SolarEdge Monitoring API."""
        try:
            data = self.api.get_current_power_flow(self.site_id)
            power_flow = data['siteCurrentPowerFlow']
        except KeyError:
            _LOGGER.error("Missing power flow data, skipping update")
            return
        except (ConnectTimeout, HTTPError):
            _LOGGER.error("Could not retrieve data, skipping update")
            return

        power_from = []
        power_to = []

        if 'connections' not in power_flow:
            _LOGGER.error("Missing connections in power flow data")
            return

        for connection in power_flow['connections']:
            power_from.append(connection['from'].lower())
            power_to.append(connection['to'].lower())

        self.data = {}
        self.attributes = {}
        self.unit = power_flow['unit']

        for key, value in power_flow.items():
            if key in ['LOAD', 'PV', 'GRID', 'STORAGE']:
                self.data[key] = value['currentPower']
                self.attributes[key] = {'status': value['status']}

            if key in ['GRID']:
                export = key.lower() in power_to
                self.data[key] *= -1 if export else 1
                self.attributes[key]['flow'] = ('export' if export
                                                else 'import')

            if key in ['STORAGE']:
                charge = key.lower() in power_to
                self.data[key] *= -1 if charge else 1
                self.attributes[key]['flow'] = ('charge' if charge
                                                else 'discharge')

        _LOGGER.debug("Updated SolarEdge power flow: %s, %s",
                      self.data, self.attributes)
