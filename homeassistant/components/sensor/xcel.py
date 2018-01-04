"""
Support for Xcel Energy energy information sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.xcel/
"""
from datetime import timedelta
from logging import getLogger

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS, CONF_PASSWORD, CONF_USERNAME
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle, slugify

REQUIREMENTS = ['pyxcel==1.2.0']

_LOGGER = getLogger(__name__)

CATEGORY_ELECTRICITY = 'ELECTRICITY-1'
CATEGORY_GAS = 'NATURAL GAS-1'

ATTR_BALANCE_AVERAGE = '_average'
ATTR_BALANCE_LAST_AMOUNT = 'last_payment_amount'
ATTR_BALANCE_LAST_DATE = 'last_payment_date'
ATTR_BALANCE_NEXT_DATE = 'next_payment_date'
ATTR_BALANCE_OVERDUE = 'payment_overdue'
ATTR_COMPARISON_ALL_NEIGHBORS = 'all_neighbors_amount'
ATTR_COMPARISON_EFFICIENT_NEIGHBORS = 'efficient_neighbors_amount'
ATTR_COMPARISON_YOU = 'your_amount'
ATTR_COST = 'cost'
ATTR_EMISSIONS = 'emissions'

DEFAULT_ATTRIBUTION = "Data provided by Xcel Energy®"

CONF_MONITORED_PREMISES = 'monitored_premises'

CONDITIONS = {
    'average_temperature': (
        'ReadSensor',
        {'category': CATEGORY_ELECTRICITY, 'label': 'Average Temperature'},
        'Average Temperature',
        'mdi:thermometer'
    ),
    'balance_info': (
        'BalanceInfoSensor',
        None,
        'Current Balance',
        'mdi:credit-card'
    ),
    'electric_commodity_adjustment_off_peak': (
        'ReadSensor',
        {'category': CATEGORY_ELECTRICITY, 'label': 'ECA Off-Peak'},
        'Electric Commodity Adjustment (Off Peak)',
        'mdi:flash'
    ),
    'electric_commodity_adjustment_on_peak': (
        'ReadSensor',
        {'category': CATEGORY_ELECTRICITY, 'label': 'ECA On-Peak'},
        'Electric Commodity Adjustment (On Peak)',
        'mdi:flash'
    ),
    'electricity_efficiency_comparison': (
        'EfficiencyComparisonSensor',
        {'comparator': 'Electricity'},
        'Electricity Comparison',
        'mdi:flash'
    ),
    'electricity_usage': (
        'UsageSensor',
        {'category': CATEGORY_ELECTRICITY},
        'Electricity Usage',
        'mdi:flash'
    ),
    'energy_efficiency_comparison': (
        'EfficiencyComparisonSensor',
        {'comparator': 'Energy'},
        'Energy Comparison',
        'mdi:power-plug'
    ),
    'natural_gas_efficiency_comparison': (
        'EfficiencyComparisonSensor',
        {'comparator': 'Natural Gas'},
        'Natural Gas Comparison',
        'mdi:gas-cylinder'
    ),
    'natural_gas_usage': (
        'UsageSensor',
        {'category': CATEGORY_GAS},
        'Natural Gas Usage',
        'mdi:gas-cylinder'
    ),
    'off_peak_energy': (
        'ReadSensor',
        {'category': CATEGORY_ELECTRICITY, 'label': 'Off Peak Energy'},
        'Off Peak Energy',
        'mdi:flash'
    ),
    'on_peak_energy': (
        'ReadSensor',
        {'category': CATEGORY_ELECTRICITY, 'label': 'On Peak Energy'},
        'On Peak Energy',
        'mdi:flash'
    ),
    'premise_grade': (
        'PremiseGradeSensor',
        None,
        'Premise Grade',
        'mdi:star'
    ),
    'shoulder_peak_energy': (
        'ReadSensor',
        {'category': CATEGORY_ELECTRICITY, 'label': 'Shoulder Peak Energy'},
        'Shoulder Peak Energy',
        'mdi:flash'
    ),
    'total_energy_interval': (
        'ReadSensor',
        {'category': CATEGORY_ELECTRICITY, 'label': 'Total Energy (interval)'},
        'Total Energy (Interval)',
        'mdi:flash'
    ),
    'total_energy_measured': (
        'ReadSensor',
        {'category': CATEGORY_ELECTRICITY, 'label': 'Total Energy (measured)'},
        'Total Energy (Measured)',
        'mdi:flash'
    ),
}

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(CONDITIONS)]),
    vol.Optional(CONF_MONITORED_PREMISES):
        vol.All(cv.ensure_list, [cv.positive_int]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Configure the platform and add the sensors."""
    import pyxcel as xcel

    _LOGGER.debug('Configuration data: %s', config)

    monitored_premises = config.get(CONF_MONITORED_PREMISES, None)
    client = xcel.Client(config[CONF_USERNAME], config[CONF_PASSWORD])
    account_data = XcelAccountData(client)
    account_data.update()

    if account_data.overview:
        sensors = []
        for premise in [
                p for p in account_data.overview.get('premises', [])
                if not monitored_premises or p['number'] in monitored_premises
        ]:
            usage_data = XcelUsageData(client, premise['number'])
            usage_data.update()

            for condition in config.get(CONF_MONITORED_CONDITIONS, []):
                sensor_class, params, name, icon = CONDITIONS[condition]
                sensors.append(globals()[sensor_class](
                    params,
                    account_data,
                    usage_data,
                    name,
                    icon))

        add_devices(sensors, True)
    else:
        _LOGGER.error('There was an error creating the Xcel sensors')


def merge_two_dicts(dict1, dict2):
    """Merge two dicts into a new dict as a shallow copy."""
    final = dict1.copy()
    final.update(dict2)
    return final


class BaseSensor(Entity):
    """Define a base class for all of our sensors."""

    def __init__(self, params, account_data, usage_data, name, icon):
        """Initialize the sensor."""
        self._icon = icon
        self._name = name
        self._params = params
        self._state = None
        self._unit = None
        self.account_data = account_data
        self.usage_data = usage_data

        if self.account_data.overview:
            self._premise = [
                p for p in self.account_data.overview['premises']
                if p['number'] == self.usage_data.premise_number
            ][0]
        else:
            self._premise = None

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit


class BalanceInfoSensor(BaseSensor):
    """Define a class to present payment information."""

    def __init__(self, premise_number, params, data, name, icon):
        """Initialize."""
        super().__init__(premise_number, params, data, name, icon)

        self._averages = None

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self.account_data.overview:
            attrs = {
                ATTR_BALANCE_LAST_AMOUNT:
                    self.account_data.overview['lastPaymentAmt'],
                ATTR_BALANCE_LAST_DATE:
                    self.account_data.overview['lastPaymentDate'],
                ATTR_BALANCE_NEXT_DATE:
                    self.account_data.overview['dueDate'],
                ATTR_BALANCE_OVERDUE:
                    self.account_data.overview['overdue']
            }
        else:
            attrs = {}

        for year, average in self._averages.items():
            attrs['{0}{1}'.format(year, ATTR_BALANCE_AVERAGE)] = average

        return merge_two_dicts(attrs, super().device_state_attributes)

    @staticmethod
    def _calculate_averages(series_data):
        """Calculate the average bill per year."""
        averages = {}

        for series in series_data:
            amounts = [float(f) for f in series['data']]
            averages[series['label']] = round(sum(amounts) / len(amounts), 2)

        return averages

    def update(self):
        """Update the status of the sensor."""
        self.account_data.update()

        if self.account_data.overview:
            self._averages = self._calculate_averages(
                self.account_data.overview['trendData']['series'])
            self._state = self.account_data.overview['currentBalance']
            self._unit = '$'
        else:
            self._averages = {}
            self._state = None
            self._unit = None


class EfficiencyComparisonSensor(BaseSensor):
    """Define a sensor for comparison data."""

    def __init__(self, premise_number, params, data, name, icon):
        """Initialize."""
        super().__init__(premise_number, params, data, name, icon)

        self._comparator = self._params['comparator']
        self._comparison = None
        self._en = None
        self._you = None

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attrs = {}

        if self._comparison:
            attrs = {
                ATTR_COMPARISON_ALL_NEIGHBORS:
                self._comparison['allNeighbors'],
                ATTR_COMPARISON_EFFICIENT_NEIGHBORS: self._en,
                ATTR_COMPARISON_YOU: self._you
            }
        else:
            attrs = {}

        return merge_two_dicts(attrs, super().device_state_attributes)

    def update(self):
        """Update the status of the sensor."""
        self.account_data.update()

        try:
            self._comparison = [
                c for c in self._premise['comparisons']
                if c['name'] == self._comparator
            ][0]
            self._en = int(self._comparison['efficientNeighbors'])
            self._you = int(self._comparison['you'])

            self._state = round((self._en - self._you) / self._en * 100)
            self._unit = '%'
        except IndexError:
            self._state = None
            self._unit = None
        except KeyError:
            self._state = None
            self._unit = None


class PremiseGradeSensor(BaseSensor):
    """Define a class to present the overall "grade" of a premise."""

    def update(self):
        """Update the status of the sensor."""
        self.account_data.update()

        if self._premise:
            self._state = self._premise['grade']
        else:
            self._state = None


class ReadSensor(BaseSensor):
    """Define a sensor to show invidiual "read" data."""

    def __init__(self, premise_number, params, data, name, icon):
        """Initialize."""
        super().__init__(premise_number, params, data, name, icon)

        self._category = self._params['category']
        self._label = self._params['label']
        self._attrs = {}

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return merge_two_dicts(self._attrs, super().device_state_attributes)

    def update(self):
        """Update the status of the sensor."""
        self.usage_data.update()

        try:
            category = [
                s for s in self.usage_data.data['services']
                if s['name'] == self._category
            ][0]
            datapoints = [
                d for d in category['reads'][0]['details']
                if d['label'] == self._label
            ]

            # Xcel lumps multiple equivalent measurements under the same
            # label; all of that data is useful, so the simplest solution is
            # to use the first measurement as the state/unit and all the
            # others as dynamic attributes:
            self._state = datapoints[0]['amount']
            self._unit = datapoints[0]['unit']
            for attr in datapoints[1:]:
                label = slugify(attr['label'])
                attr_name = '{0}_{1}'.format(label, attr['unit'])
                self._attrs[attr_name] = attr['amount']

        except IndexError as exc:
            _LOGGER.error('Could not retrieve usage data: %s', exc)
            self._state = None
            self._unit = None
        except KeyError as exc:
            _LOGGER.error('Could not retrieve usage data: %s', exc)
            self._state = None
            self._unit = None


class UsageSensor(BaseSensor):
    """Define a sensor to show basic usage information."""

    def __init__(self, premise_number, params, data, name, icon):
        """Initialize."""
        super().__init__(premise_number, params, data, name, icon)

        self._attrs = {}
        self._category = self._params['category']

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return merge_two_dicts(self._attrs, super().device_state_attributes)

    def update(self):
        """Update the status of the sensor."""
        self.usage_data.update()

        [category] = [
            c for c in self.usage_data.data['overview']
            if c['type'] == self._category
        ]

        if category:
            self._state = category['usage']['amount']
            self._unit = category['usage']['unit']

            self._attrs[ATTR_COST] = category['cost']
            self._attrs[ATTR_EMISSIONS] = category['emissions']
        else:
            self._state = None
            self._unit = None
            self._attrs = {}


class XcelAccountData(object):
    """Define a class to hold Xcel account data."""

    def __init__(self, client):
        """Initialize."""
        self._client = client
        self.overview = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update with new Xcel data."""
        from pyxcel.exceptions import XcelSessionError

        try:
            self.overview = self._client.overview.get()
        except XcelSessionError as exc:
            self.overview = None
            _LOGGER.error('There was an error retrieving Xcel overview data')
            _LOGGER.debug(exc)


class XcelUsageData(object):
    """Define a class to hold Xcel usage data by premise."""

    def __init__(self, client, premise_number):
        """Initialize."""
        self._client = client
        self.premise_number = premise_number
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update with new Xcel data."""
        from pyxcel.exceptions import XcelSessionError

        try:
            self.data = self._client.usages.get(self.premise_number)
        except XcelSessionError as exc:
            self.data = None
            _LOGGER.error('There was an error retrieving Xcel usage data')
            _LOGGER.debug(exc)
