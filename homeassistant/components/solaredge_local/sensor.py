"""Support for SolarEdge-local Monitoring API."""
from contextlib import suppress
from copy import deepcopy
from datetime import timedelta
import logging
import statistics

from requests.exceptions import ConnectTimeout, HTTPError
from solaredge_local import SolarEdge
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_NAME,
    DEVICE_CLASS_TEMPERATURE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    FREQUENCY_HERTZ,
    POWER_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

DOMAIN = "solaredge_local"
UPDATE_DELAY = timedelta(seconds=10)

INVERTER_MODES = (
    "SHUTTING_DOWN",
    "ERROR",
    "STANDBY",
    "PAIRING",
    "POWER_PRODUCTION",
    "AC_CHARGING",
    "NOT_PAIRED",
    "NIGHT_MODE",
    "GRID_MONITORING",
    "IDLE",
)

# Supported sensor types:
# Key: ['json_key', 'name', unit, icon, attribute name]
SENSOR_TYPES = {
    "current_AC_voltage": [
        "gridvoltage",
        "Grid Voltage",
        ELECTRIC_POTENTIAL_VOLT,
        "mdi:current-ac",
        None,
    ],
    "current_DC_voltage": [
        "dcvoltage",
        "DC Voltage",
        ELECTRIC_POTENTIAL_VOLT,
        "mdi:current-dc",
        None,
    ],
    "current_frequency": [
        "gridfrequency",
        "Grid Frequency",
        FREQUENCY_HERTZ,
        "mdi:current-ac",
        None,
        None,
    ],
    "current_power": [
        "currentPower",
        "Current Power",
        POWER_WATT,
        "mdi:solar-power",
        None,
        None,
    ],
    "energy_this_month": [
        "energyThisMonth",
        "Energy This Month",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
        None,
        None,
    ],
    "energy_this_year": [
        "energyThisYear",
        "Energy This Year",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
        None,
        None,
    ],
    "energy_today": [
        "energyToday",
        "Energy Today",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
        None,
        None,
    ],
    "inverter_temperature": [
        "invertertemperature",
        "Inverter Temperature",
        TEMP_CELSIUS,
        None,
        "operating_mode",
        DEVICE_CLASS_TEMPERATURE,
    ],
    "lifetime_energy": [
        "energyTotal",
        "Lifetime Energy",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
        None,
        None,
    ],
    "optimizer_connected": [
        "optimizers",
        "Optimizers Online",
        "optimizers",
        "mdi:solar-panel",
        "optimizers_connected",
        None,
    ],
    "optimizer_current": [
        "optimizercurrent",
        "Average Optimizer Current",
        ELECTRIC_CURRENT_AMPERE,
        "mdi:solar-panel",
        None,
        None,
    ],
    "optimizer_power": [
        "optimizerpower",
        "Average Optimizer Power",
        POWER_WATT,
        "mdi:solar-panel",
        None,
        None,
    ],
    "optimizer_temperature": [
        "optimizertemperature",
        "Average Optimizer Temperature",
        TEMP_CELSIUS,
        "mdi:solar-panel",
        None,
        DEVICE_CLASS_TEMPERATURE,
    ],
    "optimizer_voltage": [
        "optimizervoltage",
        "Average Optimizer Voltage",
        ELECTRIC_POTENTIAL_VOLT,
        "mdi:solar-panel",
        None,
        None,
    ],
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
            "operating_mode",
            DEVICE_CLASS_TEMPERATURE,
        ]

    try:
        if status.metersList[0]:
            sensors["import_current_power"] = [
                "currentPowerimport",
                "current import Power",
                POWER_WATT,
                "mdi:arrow-collapse-down",
                None,
                None,
            ]
            sensors["import_meter_reading"] = [
                "totalEnergyimport",
                "total import Energy",
                ENERGY_WATT_HOUR,
                "mdi:counter",
                None,
                None,
            ]
    except IndexError:
        _LOGGER.debug("Import meter sensors are not created")

    try:
        if status.metersList[1]:
            sensors["export_current_power"] = [
                "currentPowerexport",
                "current export Power",
                POWER_WATT,
                "mdi:arrow-expand-up",
                None,
                None,
            ]
            sensors["export_meter_reading"] = [
                "totalEnergyexport",
                "total export Energy",
                ENERGY_WATT_HOUR,
                "mdi:counter",
                None,
                None,
            ]
    except IndexError:
        _LOGGER.debug("Export meter sensors are not created")

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
            sensor_info[4],
            sensor_info[5],
        )
        entities.append(sensor)

    add_entities(entities, True)


class SolarEdgeSensor(SensorEntity):
    """Representation of an SolarEdge Monitoring API sensor."""

    def __init__(
        self, platform_name, data, json_key, name, unit, icon, attr, device_class
    ):
        """Initialize the sensor."""
        self._platform_name = platform_name
        self._data = data
        self._state = None

        self._json_key = json_key
        self._name = name
        self._unit_of_measurement = unit
        self._icon = icon
        self._attr = attr
        self._attr_device_class = device_class

    @property
    def name(self):
        """Return the name."""
        return f"{self._platform_name} ({self._name})"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self._attr:
            try:
                return {self._attr: self._data.info[self._json_key]}
            except KeyError:
                return None
        return None

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
        self.info = {}

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

            self.info["optimizers"] = status.optimizersStatus.total
            self.info["invertertemperature"] = INVERTER_MODES[status.status]

            with suppress(IndexError):
                if status.metersList[1]:
                    self.data["currentPowerimport"] = status.metersList[1].currentPower
                    self.data["totalEnergyimport"] = status.metersList[1].totalEnergy

            with suppress(IndexError):
                if status.metersList[0]:
                    self.data["currentPowerexport"] = status.metersList[0].currentPower
                    self.data["totalEnergyexport"] = status.metersList[0].totalEnergy

        if maintenance.system.name:
            self.data["optimizertemperature"] = round(statistics.mean(temperature), 2)
            self.data["optimizervoltage"] = round(statistics.mean(voltage), 2)
            self.data["optimizercurrent"] = round(statistics.mean(current), 2)
            self.data["optimizerpower"] = round(power, 2)
