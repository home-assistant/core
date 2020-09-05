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
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_BAR,
    TEMP_CELSIUS,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from . import SmileGateway
from .const import (
    COOL_ICON,
    DEVICE_STATE,
    DOMAIN,
    FLAME_ICON,
    IDLE_ICON,
    SENSOR_MAP_DEVICE_CLASS,
    SENSOR_MAP_MODEL,
    SENSOR_MAP_UOM,
    UNIT_LUMEN,
)

_LOGGER = logging.getLogger(__name__)

ATTR_TEMPERATURE = [
    "Temperature",
    TEMP_CELSIUS,
    DEVICE_CLASS_TEMPERATURE,
]
ATTR_BATTERY_LEVEL = [
    "Charge",
    PERCENTAGE,
    DEVICE_CLASS_BATTERY,
]
ATTR_ILLUMINANCE = [
    "Illuminance",
    UNIT_LUMEN,
    DEVICE_CLASS_ILLUMINANCE,
]
ATTR_PRESSURE = ["Pressure", PRESSURE_BAR, DEVICE_CLASS_PRESSURE]

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
    "electricity_consumed": ["Current Consumed Power", POWER_WATT, DEVICE_CLASS_POWER],
    "electricity_produced": ["Current Produced Power", POWER_WATT, DEVICE_CLASS_POWER],
    "electricity_consumed_interval": [
        "Consumed Power Interval",
        ENERGY_WATT_HOUR,
        DEVICE_CLASS_POWER,
    ],
    "electricity_consumed_peak_interval": [
        "Consumed Power Interval",
        ENERGY_WATT_HOUR,
        DEVICE_CLASS_POWER,
    ],
    "electricity_consumed_off_peak_interval": [
        "Consumed Power Interval (off peak)",
        ENERGY_WATT_HOUR,
        DEVICE_CLASS_POWER,
    ],
    "electricity_produced_interval": [
        "Produced Power Interval",
        ENERGY_WATT_HOUR,
        DEVICE_CLASS_POWER,
    ],
    "electricity_produced_peak_interval": [
        "Produced Power Interval",
        ENERGY_WATT_HOUR,
        DEVICE_CLASS_POWER,
    ],
    "electricity_produced_off_peak_interval": [
        "Produced Power Interval (off peak)",
        ENERGY_WATT_HOUR,
        DEVICE_CLASS_POWER,
    ],
    "electricity_consumed_off_peak_point": [
        "Current Consumed Power (off peak)",
        POWER_WATT,
        DEVICE_CLASS_POWER,
    ],
    "electricity_consumed_peak_point": [
        "Current Consumed Power",
        POWER_WATT,
        DEVICE_CLASS_POWER,
    ],
    "electricity_consumed_off_peak_cumulative": [
        "Cumulative Consumed Power (off peak)",
        ENERGY_KILO_WATT_HOUR,
        DEVICE_CLASS_POWER,
    ],
    "electricity_consumed_peak_cumulative": [
        "Cumulative Consumed Power",
        ENERGY_KILO_WATT_HOUR,
        DEVICE_CLASS_POWER,
    ],
    "electricity_produced_off_peak_point": [
        "Current Consumed Power (off peak)",
        POWER_WATT,
        DEVICE_CLASS_POWER,
    ],
    "electricity_produced_peak_point": [
        "Current Consumed Power",
        POWER_WATT,
        DEVICE_CLASS_POWER,
    ],
    "electricity_produced_off_peak_cumulative": [
        "Cumulative Consumed Power (off peak)",
        ENERGY_KILO_WATT_HOUR,
        DEVICE_CLASS_POWER,
    ],
    "electricity_produced_peak_cumulative": [
        "Cumulative Consumed Power",
        ENERGY_KILO_WATT_HOUR,
        DEVICE_CLASS_POWER,
    ],
    "gas_consumed_interval": ["Current Consumed Gas", VOLUME_CUBIC_METERS, None],
    "gas_consumed_cumulative": ["Cumulative Consumed Gas", VOLUME_CUBIC_METERS, None],
    "net_electricity_point": ["Current net Power", POWER_WATT, DEVICE_CLASS_POWER],
    "net_electricity_cumulative": [
        "Cumulative net Power",
        ENERGY_KILO_WATT_HOUR,
        DEVICE_CLASS_POWER,
    ],
}

MISC_SENSOR_MAP = {
    "battery": ATTR_BATTERY_LEVEL,
    "illuminance": ATTR_ILLUMINANCE,
    "modulation_level": ["Heater Modulation Level", PERCENTAGE, None],
    "valve_position": ["Valve Position", PERCENTAGE, None],
    "water_pressure": ATTR_PRESSURE,
}

INDICATE_ACTIVE_LOCAL_DEVICE = [
    "cooling_state",
    "flame_state",
]

CUSTOM_ICONS = {
    "gas_consumed_interval": "mdi:fire",
    "gas_consumed_cumulative": "mdi:fire",
    "modulation_level": "mdi:percent",
    "valve_position": "mdi:valve",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smile sensors from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    entities = []
    all_devices = api.get_all_devices()
    single_thermostat = api.single_master_thermostat()
    for dev_id, device_properties in all_devices.items():
        data = api.get_device_data(dev_id)
        for sensor, sensor_type in {
            **TEMP_SENSOR_MAP,
            **ENERGY_SENSOR_MAP,
            **MISC_SENSOR_MAP,
        }.items():
            if data.get(sensor) is None:
                continue

            if "power" in device_properties["types"]:
                model = None

                if "plug" in device_properties["types"]:
                    model = "Metered Switch"

                entities.append(
                    PwPowerSensor(
                        api,
                        coordinator,
                        device_properties["name"],
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
                        device_properties["name"],
                        dev_id,
                        sensor,
                        sensor_type,
                    )
                )

        if single_thermostat is False:
            for state in INDICATE_ACTIVE_LOCAL_DEVICE:
                if state not in data:
                    continue

                entities.append(
                    PwAuxDeviceSensor(
                        api,
                        coordinator,
                        device_properties["name"],
                        dev_id,
                        DEVICE_STATE,
                    )
                )
                break

    async_add_entities(entities, True)


class SmileSensor(SmileGateway):
    """Represent Smile Sensors."""

    def __init__(self, api, coordinator, name, dev_id, sensor):
        """Initialise the sensor."""
        super().__init__(api, coordinator, name, dev_id)

        self._sensor = sensor

        self._dev_class = None
        self._state = None
        self._unit_of_measurement = None

        if dev_id == self._api.heater_id:
            self._entity_name = "Auxiliary"

        sensorname = sensor.replace("_", " ").title()
        self._name = f"{self._entity_name} {sensorname}"

        if dev_id == self._api.gateway_id:
            self._entity_name = f"Smile {self._entity_name}"

        self._unique_id = f"{dev_id}-{sensor}"

    @property
    def device_class(self):
        """Device class of this entity."""
        return self._dev_class

    @property
    def state(self):
        """Device class of this entity."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement


class PwThermostatSensor(SmileSensor, Entity):
    """Thermostat and climate sensor entities."""

    def __init__(self, api, coordinator, name, dev_id, sensor, sensor_type):
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, dev_id, sensor)

        self._icon = None
        self._model = sensor_type[SENSOR_MAP_MODEL]
        self._unit_of_measurement = sensor_type[SENSOR_MAP_UOM]
        self._dev_class = sensor_type[SENSOR_MAP_DEVICE_CLASS]

    @callback
    def _async_process_data(self):
        """Update the entity."""
        data = self._api.get_device_data(self._dev_id)

        if not data:
            _LOGGER.error("Received no data for device %s", self._entity_name)
            self.async_write_ha_state()
            return

        if data.get(self._sensor) is not None:
            measurement = data[self._sensor]
            if self._sensor == "battery" or self._sensor == "valve_position":
                measurement = measurement * 100
            if self._unit_of_measurement == PERCENTAGE:
                measurement = int(measurement)
            self._state = measurement
            self._icon = CUSTOM_ICONS.get(self._sensor, self._icon)

        self.async_write_ha_state()


class PwAuxDeviceSensor(SmileSensor, Entity):
    """Auxiliary sensor entities for the heating/cooling device."""

    def __init__(self, api, coordinator, name, dev_id, sensor):
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, dev_id, sensor)

        self._cooling_state = False
        self._heating_state = False
        self._icon = None

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @callback
    def _async_process_data(self):
        """Update the entity."""
        data = self._api.get_device_data(self._dev_id)

        if not data:
            _LOGGER.error("Received no data for device %s", self._entity_name)
            self.async_write_ha_state()
            return

        if data.get("heating_state") is not None:
            self._heating_state = data["heating_state"]
        if data.get("cooling_state") is not None:
            self._cooling_state = data["cooling_state"]

        self._state = "idle"
        self._icon = IDLE_ICON
        if self._heating_state:
            self._state = "heating"
            self._icon = FLAME_ICON
        if self._cooling_state:
            self._state = "cooling"
            self._icon = COOL_ICON

        self.async_write_ha_state()


class PwPowerSensor(SmileSensor, Entity):
    """Power sensor entities."""

    def __init__(self, api, coordinator, name, dev_id, sensor, sensor_type, model):
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, dev_id, sensor)

        self._icon = None
        self._model = model
        if model is None:
            self._model = sensor_type[SENSOR_MAP_MODEL]

        self._unit_of_measurement = sensor_type[SENSOR_MAP_UOM]
        self._dev_class = sensor_type[SENSOR_MAP_DEVICE_CLASS]

        if dev_id == self._api.gateway_id:
            self._model = "P1 DSMR"

    @callback
    def _async_process_data(self):
        """Update the entity."""
        data = self._api.get_device_data(self._dev_id)

        if not data:
            _LOGGER.error("Received no data for device %s", self._entity_name)
            self.async_write_ha_state()
            return

        if data.get(self._sensor) is not None:
            measurement = data[self._sensor]
            if self._unit_of_measurement == ENERGY_KILO_WATT_HOUR:
                measurement = int(measurement / 1000)
            self._state = measurement
            self._icon = CUSTOM_ICONS.get(self._sensor, self._icon)

        self.async_write_ha_state()
