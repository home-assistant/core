"""Support for SolarEdge-local Monitoring API."""
from __future__ import annotations

from contextlib import suppress
from copy import copy
from dataclasses import dataclass
from datetime import timedelta
import logging
import statistics

from requests.exceptions import ConnectTimeout, HTTPError
from solaredge_local import SolarEdge
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
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


@dataclass
class SolarEdgeLocalSensorEntityDescription(SensorEntityDescription):
    """Describes SolarEdge-local sensor entity."""

    extra_attribute: str | None = None


SENSOR_TYPES: tuple[SolarEdgeLocalSensorEntityDescription, ...] = (
    SolarEdgeLocalSensorEntityDescription(
        key="gridvoltage",
        name="Grid Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:current-ac",
    ),
    SolarEdgeLocalSensorEntityDescription(
        key="dcvoltage",
        name="DC Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:current-dc",
    ),
    SolarEdgeLocalSensorEntityDescription(
        key="gridfrequency",
        name="Grid Frequency",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        icon="mdi:current-ac",
    ),
    SolarEdgeLocalSensorEntityDescription(
        key="currentPower",
        name="Current Power",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:solar-power",
    ),
    SolarEdgeLocalSensorEntityDescription(
        key="energyThisMonth",
        name="Energy This Month",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SolarEdgeLocalSensorEntityDescription(
        key="energyThisYear",
        name="Energy This Year",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SolarEdgeLocalSensorEntityDescription(
        key="energyToday",
        name="Energy Today",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SolarEdgeLocalSensorEntityDescription(
        key="energyTotal",
        name="Lifetime Energy",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SolarEdgeLocalSensorEntityDescription(
        key="optimizers",
        name="Optimizers Online",
        native_unit_of_measurement="optimizers",
        icon="mdi:solar-panel",
        extra_attribute="optimizers_connected",
    ),
    SolarEdgeLocalSensorEntityDescription(
        key="optimizercurrent",
        name="Average Optimizer Current",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        icon="mdi:solar-panel",
    ),
    SolarEdgeLocalSensorEntityDescription(
        key="optimizerpower",
        name="Average Optimizer Power",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:solar-panel",
    ),
    SolarEdgeLocalSensorEntityDescription(
        key="optimizertemperature",
        name="Average Optimizer Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon="mdi:solar-panel",
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SolarEdgeLocalSensorEntityDescription(
        key="optimizervoltage",
        name="Average Optimizer Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:solar-panel",
    ),
)

SENSOR_TYPE_INVERTER_TEMPERATURE = SolarEdgeLocalSensorEntityDescription(
    key="invertertemperature",
    name="Inverter Temperature",
    native_unit_of_measurement=TEMP_CELSIUS,
    extra_attribute="operating_mode",
    device_class=DEVICE_CLASS_TEMPERATURE,
)

SENSOR_TYPES_ENERGY_IMPORT: tuple[SolarEdgeLocalSensorEntityDescription, ...] = (
    SolarEdgeLocalSensorEntityDescription(
        key="currentPowerimport",
        name="current import Power",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:arrow-collapse-down",
    ),
    SolarEdgeLocalSensorEntityDescription(
        key="totalEnergyimport",
        name="total import Energy",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        icon="mdi:counter",
    ),
)

SENSOR_TYPES_ENERGY_EXPORT: tuple[SolarEdgeLocalSensorEntityDescription, ...] = (
    SolarEdgeLocalSensorEntityDescription(
        key="currentPowerexport",
        name="current export Power",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:arrow-expand-up",
    ),
    SolarEdgeLocalSensorEntityDescription(
        key="totalEnergyexport",
        name="total export Energy",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        icon="mdi:counter",
    ),
)

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

    # Create solaredge data service which will retrieve and update the data.
    data = SolarEdgeData(hass, api)

    # Changing inverter temperature unit.
    inverter_temp_description = copy(SENSOR_TYPE_INVERTER_TEMPERATURE)
    if status.inverters.primary.temperature.units.farenheit:
        inverter_temp_description.native_unit_of_measurement = TEMP_FAHRENHEIT

    # Create entities
    entities = [
        SolarEdgeSensor(platform_name, data, description)
        for description in (*SENSOR_TYPES, inverter_temp_description)
    ]

    try:
        if status.metersList[0]:
            entities.extend(
                [
                    SolarEdgeSensor(platform_name, data, description)
                    for description in SENSOR_TYPES_ENERGY_IMPORT
                ]
            )
    except IndexError:
        _LOGGER.debug("Import meter sensors are not created")

    try:
        if status.metersList[1]:
            entities.extend(
                [
                    SolarEdgeSensor(platform_name, data, description)
                    for description in SENSOR_TYPES_ENERGY_EXPORT
                ]
            )
    except IndexError:
        _LOGGER.debug("Export meter sensors are not created")

    add_entities(entities, True)


class SolarEdgeSensor(SensorEntity):
    """Representation of an SolarEdge Monitoring API sensor."""

    entity_description: SolarEdgeLocalSensorEntityDescription

    def __init__(
        self,
        platform_name,
        data,
        description: SolarEdgeLocalSensorEntityDescription,
    ):
        """Initialize the sensor."""
        self.entity_description = description
        self._platform_name = platform_name
        self._data = data
        self._attr_name = f"{platform_name} ({description.name})"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if extra_attr := self.entity_description.extra_attribute:
            try:
                return {extra_attr: self._data.info[self.entity_description.key]}
            except KeyError:
                pass
        return None

    def update(self):
        """Get the latest data from the sensor and update the state."""
        self._data.update()
        self._attr_native_value = self._data.data[self.entity_description.key]


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
