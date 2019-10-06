"""Support for SolarEdge-local Monitoring API."""
import logging
from datetime import timedelta
import statistics
from copy import deepcopy

from requests.exceptions import HTTPError, ConnectTimeout
from solaredge_local import SolarEdge
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_NAME,
    POWER_WATT,
    ENERGY_WATT_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

DOMAIN = "solaredge_local"
UPDATE_DELAY = timedelta(seconds=10)

# Supported sensor types:
# Key: ['json_key', 'name', unit, icon]
SENSOR_TYPES = {
    "current_power": ["currentPower", "Current Power", POWER_WATT, "mdi:solar-power"],
    "energy_this_month": [
        "energyThisMonth",
        "Energy this month",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
    ],
    "energy_this_year": [
        "energyThisYear",
        "Energy this year",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
    ],
    "energy_today": [
        "energyToday",
        "Energy today",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
    ],
    "inverter_temperature": [
        "invertertemperature",
        "Inverter Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ],
    "lifetime_energy": [
        "energyTotal",
        "Lifetime energy",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
    ],
    "optimizer_current": [
        "optimizercurrent",
        "Average Optimizer Current",
        "A",
        "mdi:solar-panel",
    ],
    "optimizer_power": [
        "optimizerpower",
        "Average Optimizer Power",
        POWER_WATT,
        "mdi:solar-panel",
    ],
    "optimizer_temperature": [
        "optimizertemperature",
        "Average Optimizer Temperature",
        TEMP_CELSIUS,
        "mdi:solar-panel",
    ],
    "optimizer_voltage": [
        "optimizervoltage",
        "Average Optimizer Voltage",
        "V",
        "mdi:solar-panel",
    ],
    "current_DC_voltage": ["dcvoltage", "DC Voltage", "V", "mdi:current-dc"],
    "current_frequency": ["gridfrequency", "Grid Frequency", "Hz", "mdi:current-ac"],
    "current_AC_voltage": ["gridvoltage", "Grid Voltage", "V", "mdi:current-ac"],
    "optimizer_connected": ["optimizers", "Optimizers online", "optimizers", "mdi:solar-panel"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_NAME, default="SolarEdge"): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the SolarEdge Monitoring API sensor."""
    ip_address = config[CONF_IP_ADDRESS]
    platform_name = config[CONF_NAME]

    # Create new SolarEdge object to retrieve data.
    api = SolarEdge(f"http://{ip_address}/")

    # Check if api can be reached and site is active.
    try:
        status = api.get_status()
        _LOGGER.debug("Credentials correct and site is active")
    except AttributeError:
        _LOGGER.error("Missing details data in solaredge status")
        _LOGGER.debug("Status is: %s", status)
        return
    except (ConnectTimeout, HTTPError):
        _LOGGER.error("Could not retrieve details from SolarEdge API")
        return

    # Changing inverter temperature unit.
    sensors = deepcopy(SENSOR_TYPES)
    if status.inverters.primary.temperature.units.farenheit:
        sensors["inverter_temperature"] = [
            "invertertemperature",
            "Inverter Temperature",
            TEMP_FAHRENHEIT,
            "mdi:thermometer",
        ]

    # Create solaredge data service which will retrieve and update the data.
    data = SolarEdgeData(hass, api)

    # Create a new sensor for each sensor type.
    entities = []
    for sensor_info in sensors.values():
        sensor = SolarEdgeSensor(
            platform_name,
            data,
            sensor_info[0],
            sensor_info[1],
            sensor_info[2],
            sensor_info[3],
        )
        entities.append(sensor)

    add_entities(entities, True)


class SolarEdgeSensor(Entity):
    """Representation of an SolarEdge Monitoring API sensor."""

    def __init__(self, platform_name, data, json_key, name, unit, icon):
        """Initialize the sensor."""
        self._platform_name = platform_name
        self._data = data
        self._state = None

        self._json_key = json_key
        self._name = name
        self._unit_of_measurement = unit
        self._icon = icon

    @property
    def name(self):
        """Return the name."""
        return f"{self._platform_name} ({self._name})"

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

    def update(self):
        """Get the latest data from the sensor and update the state."""
        self._data.update()
        self._state = self._data.data[self._json_key]


class SolarEdgeData:
    """Get and update the latest data."""

    def __init__(self, hass, api):
        """Initialize the data object."""
        self.hass = hass
        self.api = api
        self.data = {}

    @Throttle(UPDATE_DELAY)
    def update(self):
        """Update the data from the SolarEdge Monitoring API."""
        try:
            status = self.api.get_status()
            _LOGGER.debug("Status from SolarEdge: %s", status)
        except ConnectTimeout:
            _LOGGER.error("Connection timeout, skipping update")
            return
        except HTTPError:
            _LOGGER.error("Could not retrieve status, skipping update")
            return

        try:
            maintenance = self.api.get_maintenance()
            _LOGGER.debug("Maintenance from SolarEdge: %s", maintenance)
        except ConnectTimeout:
            _LOGGER.error("Connection timeout, skipping update")
            return
        except HTTPError:
            _LOGGER.error("Could not retrieve maintenance, skipping update")
            return

        temperature = []
        voltage = []
        current = []
        power = 0

        for optimizer in maintenance.diagnostics.inverters.primary.optimizer:
            if not optimizer.online:
                continue
            temperature.append(optimizer.temperature.value)
            voltage.append(optimizer.inputV)
            current.append(optimizer.inputC)

        if not voltage:
            temperature.append(0)
            voltage.append(0)
            current.append(0)
        else:
            power = statistics.mean(voltage) * statistics.mean(current)

        if status.sn:
            self.data["energyTotal"] = round(status.energy.total, 2)
            self.data["energyThisYear"] = round(status.energy.thisYear, 2)
            self.data["energyThisMonth"] = round(status.energy.thisMonth, 2)
            self.data["energyToday"] = round(status.energy.today, 2)
            self.data["currentPower"] = round(status.powerWatt, 2)
            self.data["invertertemperature"] = round(
                status.inverters.primary.temperature.value, 2
            )
            self.data["dcvoltage"] = round(status.inverters.primary.voltage, 2)
            self.data["gridfrequency"] = round(status.frequencyHz, 2)
            self.data["gridvoltage"] = round(status.voltage, 2)
            self.data["optimizers"] = status.optimizersStatus.online
        if maintenance.system.name:
            self.data["optimizertemperature"] = round(statistics.mean(temperature), 2)
            self.data["optimizervoltage"] = round(statistics.mean(voltage), 2)
            self.data["optimizercurrent"] = round(statistics.mean(current), 2)
            self.data["optimizerpower"] = round(power, 2)
