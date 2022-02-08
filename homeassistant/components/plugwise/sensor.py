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

    entities: list[PlugwiseSensorEnity] = []
    for device_id, device in coordinator.data.devices.items():
        for description in SENSORS:
            if (
                "sensors" not in device
                or device["sensors"].get(description.key) is None
            ):
                continue

            entities.append(
                PlugwiseSensorEnity(
                    api,
                    coordinator,
                    device_id,
                    description,
                )
            )

        if coordinator.data.gateway["single_master_thermostat"] is False:
            # These sensors should actually be binary sensors.
            for description in INDICATE_ACTIVE_LOCAL_DEVICE_SENSORS:
                if description.key not in device:
                    continue

                entities.append(
                    PlugwiseAuxSensorEntity(
                        api,
                        coordinator,
                        device_id,
                        description,
                    )
                )
                break

    async_add_entities(entities, True)


class PlugwiseSensorEnity(PlugwiseEntity, SensorEntity):
    """Represent Plugwise Sensors."""

    def __init__(
        self,
        api: Smile,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._api = api
        self._attr_unique_id = f"{device_id}-{description.key}"
        self._attr_name = (
            f"{coordinator.data.devices[device_id].get('name', '')} {description.name}"
        ).lstrip()

    @callback
    def _async_process_data(self) -> None:
        """Update the entity."""
        if not (data := self.coordinator.data.devices.get(self._dev_id)):
            LOGGER.error("Received no data for device %s", self._dev_id)
            self.async_write_ha_state()
            return

        self._attr_native_value = data["sensors"].get(self.entity_description.key)
        self.async_write_ha_state()


class PlugwiseAuxSensorEntity(PlugwiseSensorEnity):
    """Auxiliary Device Sensors."""

    _cooling_state = False
    _heating_state = False

    @callback
    def _async_process_data(self) -> None:
        """Update the entity."""
        if not (data := self.coordinator.data.devices.get(self._dev_id)):
            LOGGER.error("Received no data for device %s", self._dev_id)
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
