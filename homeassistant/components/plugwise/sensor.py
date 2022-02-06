"""Plugwise Sensor component for Home Assistant."""
from __future__ import annotations

from plugwise.smile import Smile

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_BAR,
    TEMP_CELSIUS,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COOL_ICON,
    COORDINATOR,
    DEVICE_STATE,
    DOMAIN,
    FLAME_ICON,
    IDLE_ICON,
    LOGGER,
    SENSOR_MAP_DEVICE_CLASS,
    SENSOR_MAP_MODEL,
    SENSOR_MAP_STATE_CLASS,
    SENSOR_MAP_UOM,
    UNIT_LUMEN,
)
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity

ATTR_TEMPERATURE = [
    "Temperature",
    TEMP_CELSIUS,
    SensorDeviceClass.TEMPERATURE,
    SensorStateClass.MEASUREMENT,
]
ATTR_BATTERY_LEVEL = [
    "Charge",
    PERCENTAGE,
    SensorDeviceClass.BATTERY,
    SensorStateClass.MEASUREMENT,
]
ATTR_ILLUMINANCE = [
    "Illuminance",
    UNIT_LUMEN,
    SensorDeviceClass.ILLUMINANCE,
    SensorStateClass.MEASUREMENT,
]
ATTR_PRESSURE = [
    "Pressure",
    PRESSURE_BAR,
    SensorDeviceClass.PRESSURE,
    SensorStateClass.MEASUREMENT,
]

TEMP_SENSOR_MAP: dict[str, list] = {
    "setpoint": ATTR_TEMPERATURE,
    "temperature": ATTR_TEMPERATURE,
    "intended_boiler_temperature": ATTR_TEMPERATURE,
    "temperature_difference": ATTR_TEMPERATURE,
    "outdoor_temperature": ATTR_TEMPERATURE,
    "water_temperature": ATTR_TEMPERATURE,
    "return_temperature": ATTR_TEMPERATURE,
}

ENERGY_SENSOR_MAP: dict[str, list] = {
    "electricity_consumed": [
        "Current Consumed Power",
        POWER_WATT,
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
    ],
    "electricity_produced": [
        "Current Produced Power",
        POWER_WATT,
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
    ],
    "electricity_consumed_interval": [
        "Consumed Power Interval",
        ENERGY_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL,
    ],
    "electricity_consumed_peak_interval": [
        "Consumed Power Interval",
        ENERGY_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL,
    ],
    "electricity_consumed_off_peak_interval": [
        "Consumed Power Interval (off peak)",
        ENERGY_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL,
    ],
    "electricity_produced_interval": [
        "Produced Power Interval",
        ENERGY_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL,
    ],
    "electricity_produced_peak_interval": [
        "Produced Power Interval",
        ENERGY_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL,
    ],
    "electricity_produced_off_peak_interval": [
        "Produced Power Interval (off peak)",
        ENERGY_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL,
    ],
    "electricity_consumed_off_peak_point": [
        "Current Consumed Power (off peak)",
        POWER_WATT,
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
    ],
    "electricity_consumed_peak_point": [
        "Current Consumed Power",
        POWER_WATT,
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
    ],
    "electricity_consumed_off_peak_cumulative": [
        "Cumulative Consumed Power (off peak)",
        ENERGY_KILO_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
    ],
    "electricity_consumed_peak_cumulative": [
        "Cumulative Consumed Power",
        ENERGY_KILO_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
    ],
    "electricity_produced_off_peak_point": [
        "Current Produced Power (off peak)",
        POWER_WATT,
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
    ],
    "electricity_produced_peak_point": [
        "Current Produced Power",
        POWER_WATT,
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
    ],
    "electricity_produced_off_peak_cumulative": [
        "Cumulative Produced Power (off peak)",
        ENERGY_KILO_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
    ],
    "electricity_produced_peak_cumulative": [
        "Cumulative Produced Power",
        ENERGY_KILO_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
    ],
    "gas_consumed_interval": [
        "Current Consumed Gas Interval",
        VOLUME_CUBIC_METERS,
        SensorDeviceClass.GAS,
        SensorStateClass.TOTAL,
    ],
    "gas_consumed_cumulative": [
        "Consumed Gas",
        VOLUME_CUBIC_METERS,
        SensorDeviceClass.GAS,
        SensorStateClass.TOTAL_INCREASING,
    ],
    "net_electricity_point": [
        "Current net Power",
        POWER_WATT,
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
    ],
    "net_electricity_cumulative": [
        "Cumulative net Power",
        ENERGY_KILO_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL,
    ],
}

MISC_SENSOR_MAP: dict[str, list] = {
    "battery": ATTR_BATTERY_LEVEL,
    "illuminance": ATTR_ILLUMINANCE,
    "modulation_level": [
        "Heater Modulation Level",
        PERCENTAGE,
        None,
        SensorStateClass.MEASUREMENT,
    ],
    "valve_position": [
        "Valve Position",
        PERCENTAGE,
        None,
        SensorStateClass.MEASUREMENT,
    ],
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile sensors from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    entities: list[SmileSensor] = []
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


class SmileSensor(PlugwiseEntity, SensorEntity):
    """Represent Smile Sensors."""

    def __init__(
        self,
        api: Smile,
        coordinator: PlugwiseDataUpdateCoordinator,
        name: str,
        dev_id: str,
        sensor: str,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(api, coordinator, name, dev_id)
        self._attr_unique_id = f"{dev_id}-{sensor}"
        self._sensor = sensor

        if dev_id == self._api.heater_id:
            self._entity_name = "Auxiliary"

        sensorname = sensor.replace("_", " ").title()
        self._name = f"{self._entity_name} {sensorname}"

        if dev_id == self._api.gateway_id:
            self._entity_name = f"Smile {self._entity_name}"


class PwThermostatSensor(SmileSensor):
    """Thermostat (or generic) sensor devices."""

    def __init__(
        self,
        api: Smile,
        coordinator: PlugwiseDataUpdateCoordinator,
        name: str,
        dev_id: str,
        sensor: str,
        sensor_type: list[str],
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, dev_id, sensor)

        self._model = sensor_type[SENSOR_MAP_MODEL]
        self._attr_native_unit_of_measurement = sensor_type[SENSOR_MAP_UOM]
        self._attr_device_class = sensor_type[SENSOR_MAP_DEVICE_CLASS]
        self._attr_state_class = sensor_type[SENSOR_MAP_STATE_CLASS]

    @callback
    def _async_process_data(self) -> None:
        """Update the entity."""
        if not (data := self._api.get_device_data(self._dev_id)):
            LOGGER.error("Received no data for device %s", self._entity_name)
            self.async_write_ha_state()
            return

        if data.get(self._sensor) is not None:
            self._attr_native_value = data[self._sensor]
            self._attr_icon = CUSTOM_ICONS.get(self._sensor, self.icon)

        self.async_write_ha_state()


class PwAuxDeviceSensor(SmileSensor):
    """Auxiliary Device Sensors."""

    def __init__(
        self,
        api: Smile,
        coordinator: PlugwiseDataUpdateCoordinator,
        name: str,
        dev_id: str,
        sensor: str,
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, dev_id, sensor)

        self._cooling_state = False
        self._heating_state = False

    @callback
    def _async_process_data(self) -> None:
        """Update the entity."""
        if not (data := self._api.get_device_data(self._dev_id)):
            LOGGER.error("Received no data for device %s", self._entity_name)
            self.async_write_ha_state()
            return

        if data.get("heating_state") is not None:
            self._heating_state = data["heating_state"]
        if data.get("cooling_state") is not None:
            self._cooling_state = data["cooling_state"]

        self._attr_native_value = "idle"
        self._attr_icon = IDLE_ICON
        if self._heating_state:
            self._attr_native_value = "heating"
            self._attr_icon = FLAME_ICON
        if self._cooling_state:
            self._attr_native_value = "cooling"
            self._attr_icon = COOL_ICON

        self.async_write_ha_state()


class PwPowerSensor(SmileSensor):
    """Power sensor entities."""

    def __init__(
        self,
        api: Smile,
        coordinator: PlugwiseDataUpdateCoordinator,
        name: str,
        dev_id: str,
        sensor: str,
        sensor_type: list[str],
        model: str | None,
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, dev_id, sensor)

        self._model = model
        if model is None:
            self._model = sensor_type[SENSOR_MAP_MODEL]

        self._attr_native_unit_of_measurement = sensor_type[SENSOR_MAP_UOM]
        self._attr_device_class = sensor_type[SENSOR_MAP_DEVICE_CLASS]
        self._attr_state_class = sensor_type[SENSOR_MAP_STATE_CLASS]

        if dev_id == self._api.gateway_id:
            self._model = "P1 DSMR"

    @callback
    def _async_process_data(self) -> None:
        """Update the entity."""
        if not (data := self._api.get_device_data(self._dev_id)):
            LOGGER.error("Received no data for device %s", self._entity_name)
            self.async_write_ha_state()
            return

        if data.get(self._sensor) is not None:
            self._attr_native_value = data[self._sensor]
            self._attr_icon = CUSTOM_ICONS.get(self._sensor, self.icon)

        self.async_write_ha_state()
