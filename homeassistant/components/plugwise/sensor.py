"""Plugwise Sensor component for Home Assistant."""

import logging

from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    POWER_WATT,
    PRESSURE_BAR,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
    VOLUME_CUBIC_METERS,
)
from homeassistant.helpers.entity import Entity

from . import SmileGateway
from .const import (
    COOL_ICON,
    DEVICE_STATE,
    DOMAIN,
    FLAME_ICON,
    IDLE_ICON,
    SENSOR_MAP_DEVICE_CLASS,
    SENSOR_MAP_ICON,
    SENSOR_MAP_MODEL,
    SENSOR_MAP_UOM,
    UNIT_LUMEN,
)

_LOGGER = logging.getLogger(__name__)

ATTR_TEMPERATURE = [
    "Temperature",
    TEMP_CELSIUS,
    DEVICE_CLASS_TEMPERATURE,
    "mdi:thermometer",
]
ATTR_BATTERY_LEVEL = [
    "Charge",
    UNIT_PERCENTAGE,
    DEVICE_CLASS_BATTERY,
    "mdi:battery-high",
]
ATTR_ILLUMINANCE = [
    "Illuminance",
    UNIT_LUMEN,
    DEVICE_CLASS_ILLUMINANCE,
    "mdi:lightbulb-on-outline",
]
ATTR_PRESSURE = ["Pressure", PRESSURE_BAR, DEVICE_CLASS_PRESSURE, "mdi:water"]

TEMP_SENSOR_MAP = {
    "setpoint": ATTR_TEMPERATURE,
    "temperature": ATTR_TEMPERATURE,
    "intended_boiler_temperature": ATTR_TEMPERATURE,
    "temperature_difference": ATTR_TEMPERATURE,
    "outdoor_temperature": ATTR_TEMPERATURE,
    "water_temperature": ATTR_TEMPERATURE,
    "return_temperature": ATTR_TEMPERATURE,
}

ENERGY_SENSOR_MAP = {
    "electricity_consumed": [
        "Current Consumed Power",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        "mdi:flash",
    ],
    "electricity_produced": [
        "Current Produced Power",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        "mdi:flash",
    ],
    "electricity_consumed_interval": [
        "Consumed Power Interval",
        ENERGY_WATT_HOUR,
        DEVICE_CLASS_POWER,
        "mdi:flash",
    ],
    "electricity_produced_interval": [
        "Produced Power Interval",
        ENERGY_WATT_HOUR,
        DEVICE_CLASS_POWER,
        "mdi:flash",
    ],
    "electricity_consumed_off_peak_point": [
        "Current Consumed Power (off peak)",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        "mdi:flash",
    ],
    "electricity_consumed_peak_point": [
        "Current Consumed Power",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        "mdi:flash",
    ],
    "electricity_consumed_off_peak_cumulative": [
        "Cumulative Consumed Power (off peak)",
        ENERGY_KILO_WATT_HOUR,
        DEVICE_CLASS_POWER,
        "mdi:gauge",
    ],
    "electricity_consumed_peak_cumulative": [
        "Cumulative Consumed Power",
        ENERGY_KILO_WATT_HOUR,
        DEVICE_CLASS_POWER,
        "mdi:gauge",
    ],
    "electricity_produced_off_peak_point": [
        "Current Consumed Power (off peak)",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        "mdi:white-balance-sunny",
    ],
    "electricity_produced_peak_point": [
        "Current Consumed Power",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        "mdi:white-balance-sunny",
    ],
    "electricity_produced_off_peak_cumulative": [
        "Cumulative Consumed Power (off peak)",
        ENERGY_KILO_WATT_HOUR,
        DEVICE_CLASS_POWER,
        "mdi:gauge",
    ],
    "electricity_produced_peak_cumulative": [
        "Cumulative Consumed Power",
        ENERGY_KILO_WATT_HOUR,
        DEVICE_CLASS_POWER,
        "mdi:gauge",
    ],
    "gas_consumed_interval": [
        "Current Consumed Gas",
        VOLUME_CUBIC_METERS,
        None,
        "mdi:gas-cylinder",
    ],
    "gas_consumed_cumulative": [
        "Cumulative Consumed Gas",
        VOLUME_CUBIC_METERS,
        None,
        "mdi:gauge",
    ],
    "net_electricity_point": [
        "Current net Power",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        "mdi:solar-power",
    ],
    "net_electricity_cumulative": [
        "Cumulative net Power",
        ENERGY_KILO_WATT_HOUR,
        DEVICE_CLASS_POWER,
        "mdi:gauge",
    ],
}

MISC_SENSOR_MAP = {
    "battery": ATTR_BATTERY_LEVEL,
    "illuminance": ATTR_ILLUMINANCE,
    "modulation_level": [
        "Heater Modulation Level",
        UNIT_PERCENTAGE,
        "modulation",
        "mdi:percent",
    ],
    "valve_position": ["Valve Position", UNIT_PERCENTAGE, None, "mdi:valve"],
    "water_pressure": ATTR_PRESSURE,
}

INDICATE_ACTIVE_LOCAL_DEVICE = [
    "cooling_state",
    "flame_state",
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smile sensors from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    entities = []
    all_devices = api.get_all_devices()
    single_thermostat = api.single_master_thermostat()
    for dev_id, entity in all_devices.items():
        data = api.get_device_data(dev_id)
        for sensor, sensor_type in {
            **TEMP_SENSOR_MAP,
            **ENERGY_SENSOR_MAP,
            **MISC_SENSOR_MAP,
        }.items():
            if sensor in data:
                if data[sensor] is None:
                    continue

                if "power" in entity["types"]:
                    model = None

                    if "plug" in entity["types"]:
                        model = "Metered Switch"

                    entities.append(
                        PwPowerSensor(
                            api,
                            coordinator,
                            entity["name"],
                            dev_id,
                            sensor,
                            sensor_type,
                            model,
                        )
                    )
                else:
                    entities.append(
                        PwThermostatSensor(
                            api,
                            coordinator,
                            entity["name"],
                            dev_id,
                            sensor,
                            sensor_type,
                        )
                    )
                _LOGGER.info("Added sensor.%s", entity["name"])

        if single_thermostat is False:
            for state in INDICATE_ACTIVE_LOCAL_DEVICE:
                if state in data:
                    entities.append(
                        PwThermostatSensor(
                            api,
                            coordinator,
                            entity["name"],
                            dev_id,
                            DEVICE_STATE,
                            None,
                        )
                    )
                    _LOGGER.info("Added sensor.%s_state", "{}".format(entity["name"]))
                    break

    async_add_entities(entities, True)


class SmileSensor(SmileGateway):
    """Represent Smile Sensors."""

    def __init__(self, api, coordinator):
        """Initialise the sensor."""
        super().__init__(api, coordinator)

        self._dev_class = None
        self._state = None
        self._unit_of_measurement = None

    @property
    def device_class(self):
        """Device class of this entity."""
        if not self._dev_class:
            return None
        return self._dev_class

    @property
    def state(self):
        """Device class of this entity."""
        if not self._state:
            return None
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if not self._unit_of_measurement:
            return None
        return self._unit_of_measurement


class PwThermostatSensor(SmileSensor, Entity):
    """Thermostat (or generic) sensor entities."""

    def __init__(self, api, coordinator, name, dev_id, sensor, sensor_type):
        """Set up the Plugwise API."""
        super().__init__(api, coordinator)

        self._api = api
        self._gateway_id = self._api.gateway_id
        self._dev_id = dev_id
        self._sensor_type = sensor_type
        self._entity_name = name
        self._sensor = sensor

        self._state = None
        self._model = None
        self._unit_of_measurement = None
        self._heating_state = False
        self._cooling_state = False

        if self._sensor_type is not None:
            self._model = self._sensor_type[SENSOR_MAP_MODEL]
            self._unit_of_measurement = self._sensor_type[SENSOR_MAP_UOM]
            self._dev_class = self._sensor_type[SENSOR_MAP_DEVICE_CLASS]
            self._icon = self._sensor_type[SENSOR_MAP_ICON]

        if self._dev_id == self._api.heater_id:
            self._entity_name = "Auxiliary"

        sensorname = sensor.replace("_", " ").title()
        self._name = f"{self._entity_name} {sensorname}"

        if self._dev_id == self._api.gateway_id:
            self._entity_name = f"Smile {self._entity_name}"

        self._unique_id = f"{dev_id}-{sensor}"

    def _process_data(self):
        """Update the entity."""
        data = self._api.get_device_data(self._dev_id)

        if not data:
            _LOGGER.error("Received no data for device %s.", self._entity_name)
            self.async_write_ha_state()
            return

        if self._sensor in data:
            if data[self._sensor] is not None:
                measurement = data[self._sensor]
                if self._sensor == "battery" or self._sensor == "valve_position":
                    measurement = measurement * 100
                if self._unit_of_measurement == UNIT_PERCENTAGE:
                    measurement = int(measurement)
                self._state = measurement

        if "heating_state" in data:
            if data["heating_state"] is not None:
                self._heating_state = data["heating_state"]
        if "cooling_state" in data:
            if data["cooling_state"] is not None:
                self._cooling_state = data["cooling_state"]
        if self._sensor == DEVICE_STATE:
            if self._heating_state:
                self._state = "heating"
            elif self._cooling_state:
                self._state = "cooling"
            else:
                self._state = "idle"

        if self._sensor_type is None:
            self._icon = IDLE_ICON
            if self._heating_state:
                self._icon = FLAME_ICON
            if self._cooling_state:
                self._icon = COOL_ICON

        self.async_write_ha_state()


class PwPowerSensor(SmileSensor, Entity):
    """Power sensor entities."""

    def __init__(self, api, coordinator, name, dev_id, sensor, sensor_type, model):
        """Set up the Plugwise API."""
        super().__init__(api, coordinator)

        self._api = api
        self._gateway_id = self._api.gateway_id
        self._model = model
        self._entity_name = name
        self._dev_id = dev_id
        self._sensor = sensor

        self._state = None

        self._model = sensor_type[SENSOR_MAP_MODEL]
        self._unit_of_measurement = sensor_type[SENSOR_MAP_UOM]
        self._dev_class = sensor_type[SENSOR_MAP_DEVICE_CLASS]
        self._icon = sensor_type[SENSOR_MAP_ICON]

        sensorname = sensor.replace("_", " ").title()
        self._name = f"{name} {sensorname}"

        if self._dev_id == self._api.gateway_id:
            self._entity_name = f"Smile {self._entity_name}"

        self._unique_id = f"{dev_id}-{sensor}"

    def _process_data(self):
        """Update the entity."""
        data = self._api.get_device_data(self._dev_id)

        if not data:
            _LOGGER.error("Received no data for device %s.", self._entity_name)
            self.async_write_ha_state()
            return

        if self._sensor in data:
            if data[self._sensor] is not None:
                measurement = data[self._sensor]
                if self._unit_of_measurement == ENERGY_KILO_WATT_HOUR:
                    measurement = int(measurement / 1000)
                self._state = measurement

        self.async_write_ha_state()
