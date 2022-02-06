"""Plugwise Sensor component for Home Assistant."""
from __future__ import annotations

from plugwise.smile import Smile

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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
    DOMAIN,
    FLAME_ICON,
    IDLE_ICON,
    LOGGER,
    UNIT_LUMEN,
)
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="setpoint",
        name="Setpoint",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="intended_boiler_temperature",
        name="Intended Boiler Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temperature_difference",
        name="Temperature Difference",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="outdoor_temperature",
        name="Outdoor Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="water_temperature",
        name="Water Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="return_temperature",
        name="Return Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="return_temperature",
        name="Return Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="electricity_consumed",
        name="Electricity Consumed",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="electricity_produced",
        name="Electricity Produced",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="electricity_consumed_interval",
        name="Electricity Consumed Interval",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="electricity_consumed_peak_interval",
        name="Electricity Consumed Peak Interval",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="electricity_consumed_off_peak_interval",
        name="Electricity Consumed Off Peak Interval",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="electricity_produced_interval",
        name="Electricity Produced Interval",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="electricity_produced_peak_interval",
        name="Electricity Produced Peak Interval",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="electricity_produced_off_peak_interval",
        name="Electricity Produced Off Peak Interval",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="electricity_consumed_off_peak_point",
        name="Electricity Consumed Off Peak Point",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="electricity_consumed_peak_point",
        name="Electricity Consumed Peak Point",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="electricity_consumed_off_peak_cumulative",
        name="Electricity Consumed Off Peak Cumulative",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="electricity_consumed_peak_cumulative",
        name="Electricity Consumed Peak Cumulative",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="electricity_produced_off_peak_point",
        name="Electricity Produced Off Peak Point",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="electricity_produced_peak_point",
        name="Electricity Produced Peak Point",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="electricity_produced_off_peak_cumulative",
        name="Electricity Produced Off Peak Cumulative",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="electricity_produced_peak_cumulative",
        name="Electricity Produced Peak Cumulative",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="gas_consumed_interval",
        name="Gas Consumed Interval",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="gas_consumed_cumulative",
        name="Gas Consumed Cumulative",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="net_electricity_point",
        name="Net Electricity Point",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="net_electricity_cumulative",
        name="Net Electricity Cumulative",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="illuminance",
        name="Illuminance",
        native_unit_of_measurement=UNIT_LUMEN,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="modulation_level",
        name="Modulation Level",
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="valve_position",
        name="Valve Position",
        icon="mdi:valve",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="water_pressure",
        name="Water Pressure",
        native_unit_of_measurement=PRESSURE_BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

INDICATE_ACTIVE_LOCAL_DEVICE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="cooling_state",
        name="Cooling State",
    ),
    SensorEntityDescription(
        key="flame_state",
        name="Flame State",
    ),
)


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
        for description in SENSORS:
            if data.get(description.key) is None:
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
                        model,
                        description,
                    )
                )
            else:
                entities.append(
                    PwThermostatSensor(
                        api,
                        coordinator,
                        device_properties["name"],
                        dev_id,
                        description,
                    )
                )

        if single_thermostat is False:
            for description in INDICATE_ACTIVE_LOCAL_DEVICE_SENSORS:
                if description.key not in data:
                    continue

                entities.append(
                    PwAuxDeviceSensor(
                        api,
                        coordinator,
                        device_properties["name"],
                        dev_id,
                        description,
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
        description: SensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(api, coordinator, name, dev_id)
        self.entity_description = description
        self._attr_unique_id = f"{dev_id}-{description.key}"

        if dev_id == self._api.heater_id:
            self._entity_name = "Auxiliary"

        self._name = f"{self._entity_name} {description.name}"

        if dev_id == self._api.gateway_id:
            self._entity_name = f"Smile {self._entity_name}"


class PwThermostatSensor(SmileSensor):
    """Thermostat (or generic) sensor devices."""

    @callback
    def _async_process_data(self) -> None:
        """Update the entity."""
        if not (data := self._api.get_device_data(self._dev_id)):
            LOGGER.error("Received no data for device %s", self._entity_name)
            self.async_write_ha_state()
            return

        self._attr_native_value = data.get(self.entity_description.key)
        self.async_write_ha_state()


class PwAuxDeviceSensor(SmileSensor):
    """Auxiliary Device Sensors."""

    _cooling_state = False
    _heating_state = False

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
        model: str | None,
        description: SensorEntityDescription,
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, dev_id, description)
        self._model = model
        if dev_id == self._api.gateway_id:
            self._model = "P1 DSMR"

    @callback
    def _async_process_data(self) -> None:
        """Update the entity."""
        if not (data := self._api.get_device_data(self._dev_id)):
            LOGGER.error("Received no data for device %s", self._entity_name)
            self.async_write_ha_state()
            return

        self._attr_native_value = data.get(self.entity_description.key)
        self.async_write_ha_state()
