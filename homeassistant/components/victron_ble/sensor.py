"""Sensor platform for Victron BLE."""

import logging

from sensor_state_data import DeviceKey
from victron_ble_ha_parser import Keys, Units

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS = {
    Keys.AC_IN_POWER: SensorEntityDescription(
        key=Keys.AC_IN_POWER,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.AC_IN_STATE: SensorEntityDescription(
        key=Keys.AC_IN_STATE,
        device_class=SensorDeviceClass.ENUM,
        translation_key="device_state",
    ),
    Keys.AC_OUT_POWER: SensorEntityDescription(
        key=Keys.AC_OUT_POWER,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.AC_OUT_STATE: SensorEntityDescription(
        key=Keys.AC_OUT_STATE,
        device_class=SensorDeviceClass.ENUM,
        translation_key="device_state",
    ),
    Keys.ALARM: SensorEntityDescription(
        key=Keys.ALARM,
        device_class=SensorDeviceClass.ENUM,
        translation_key="alarm",
    ),
    Keys.AUX_MODE: SensorEntityDescription(
        key=Keys.AUX_MODE,
        device_class=SensorDeviceClass.ENUM,
        translation_key="aux_mode",
    ),
    Keys.BALANCER_STATUS: SensorEntityDescription(
        key=Keys.BALANCER_STATUS,
        device_class=SensorDeviceClass.ENUM,
        translation_key="balancer_status",
    ),
    Keys.BATTERY_CURRENT: SensorEntityDescription(
        key=Keys.BATTERY_CURRENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.BATTERY_TEMPERATURE: SensorEntityDescription(
        key=Keys.BATTERY_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.BATTERY_VOLTAGE: SensorEntityDescription(
        key=Keys.BATTERY_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.CHARGE_STATE: SensorEntityDescription(
        key=Keys.CHARGE_STATE,
        device_class=SensorDeviceClass.ENUM,
        translation_key="device_state",
    ),
    Keys.CHARGER_ERROR: SensorEntityDescription(
        key=Keys.CHARGER_ERROR,
        device_class=SensorDeviceClass.ENUM,
        translation_key="charger_error",
    ),
    Keys.CONSUMED_AMPERE_HOURS: SensorEntityDescription(
        key=Keys.CONSUMED_AMPERE_HOURS,
        native_unit_of_measurement=Units.ELECTRIC_CURRENT_FLOW_AMPERE_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.CURRENT: SensorEntityDescription(
        key=Keys.CURRENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.DEVICE_STATE: SensorEntityDescription(
        key=Keys.DEVICE_STATE,
        device_class=SensorDeviceClass.ENUM,
        translation_key="device_state",
    ),
    Keys.ERROR_CODE: SensorEntityDescription(
        key=Keys.ERROR_CODE,
        device_class=SensorDeviceClass.ENUM,
        translation_key="charger_error",
    ),
    Keys.EXTERNAL_DEVICE_LOAD: SensorEntityDescription(
        key=Keys.EXTERNAL_DEVICE_LOAD,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.INPUT_VOLTAGE: SensorEntityDescription(
        key=Keys.INPUT_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.METER_TYPE: SensorEntityDescription(
        key=Keys.METER_TYPE,
        device_class=SensorDeviceClass.ENUM,
        translation_key="meter_type",
    ),
    Keys.MIDPOINT_VOLTAGE: SensorEntityDescription(
        key=Keys.MIDPOINT_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.OFF_REASON: SensorEntityDescription(
        key=Keys.OFF_REASON,
        device_class=SensorDeviceClass.ENUM,
        translation_key="off_reason",
    ),
    Keys.OUTPUT_STATE: SensorEntityDescription(
        key=Keys.OUTPUT_STATE,
        device_class=SensorDeviceClass.ENUM,
        translation_key="output_state",
    ),
    Keys.OUTPUT_VOLTAGE: SensorEntityDescription(
        key=Keys.OUTPUT_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.REMAINING_MINUTES: SensorEntityDescription(
        key=Keys.REMAINING_MINUTES,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorDeviceClass.SIGNAL_STRENGTH: SensorEntityDescription(
        key=SensorDeviceClass.SIGNAL_STRENGTH.value,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.SOLAR_POWER: SensorEntityDescription(
        key=Keys.SOLAR_POWER,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.STARTER_VOLTAGE: SensorEntityDescription(
        key=Keys.STARTER_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.STATE_OF_CHARGE: SensorEntityDescription(
        key=Keys.STATE_OF_CHARGE,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.TEMPERATURE: SensorEntityDescription(
        key=Keys.TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.VOLTAGE: SensorEntityDescription(
        key=Keys.VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Keys.WARNING: SensorEntityDescription(
        key=Keys.WARNING,
        device_class=SensorDeviceClass.ENUM,
        translation_key="alarm",
    ),
    Keys.YIELD_TODAY: SensorEntityDescription(
        key=Keys.YIELD_TODAY,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
}

for i in range(1, 8):
    cell_key = getattr(Keys, f"CELL_{i}_VOLTAGE")
    SENSOR_DESCRIPTIONS[cell_key] = SensorEntityDescription(
        key=cell_key,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    )


def _device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)


def sensor_update_to_bluetooth_data_update(
    sensor_update,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            _device_key_to_bluetooth_entity_key(device_key): SENSOR_DESCRIPTIONS[
                device_key.key
            ]
            for device_key in sensor_update.entity_descriptions
        },
        entity_data={
            _device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
        entity_names={
            _device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Victron BLE sensor."""
    coordinator: PassiveBluetoothProcessorCoordinator = entry.runtime_data
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            VictronBLESensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class VictronBLESensorEntity(PassiveBluetoothProcessorEntity, SensorEntity):
    """Representation of Victron BLE sensor."""

    @property
    def native_value(self) -> float | int | str | None:
        """Return the state of the sensor."""
        return self.processor.entity_data.get(self.entity_key)
