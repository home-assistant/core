"""Support for xiaomi ble sensors."""
from __future__ import annotations

from typing import Optional, Union

from xiaomi_ble import (
    DeviceClass,
    DeviceKey,
    SensorDeviceInfo,
    SensorUpdate,
    Units,
    XiaomiBluetoothDeviceData,
)
from xiaomi_ble.parser import EncryptionScheme

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
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
from homeassistant.const import (
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    CONDUCTIVITY,
    ELECTRIC_POTENTIAL_VOLT,
    LIGHT_LUX,
    PERCENTAGE,
    PRESSURE_MBAR,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

SENSOR_DESCRIPTIONS = {
    (DeviceClass.TEMPERATURE, Units.TEMP_CELSIUS): SensorEntityDescription(
        key=f"{DeviceClass.TEMPERATURE}_{Units.TEMP_CELSIUS}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (DeviceClass.HUMIDITY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{DeviceClass.HUMIDITY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (DeviceClass.ILLUMINANCE, Units.LIGHT_LUX): SensorEntityDescription(
        key=f"{DeviceClass.ILLUMINANCE}_{Units.LIGHT_LUX}",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (DeviceClass.PRESSURE, Units.PRESSURE_MBAR): SensorEntityDescription(
        key=f"{DeviceClass.PRESSURE}_{Units.PRESSURE_MBAR}",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_MBAR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (DeviceClass.BATTERY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{DeviceClass.BATTERY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (DeviceClass.VOLTAGE, Units.ELECTRIC_POTENTIAL_VOLT): SensorEntityDescription(
        key=str(Units.ELECTRIC_POTENTIAL_VOLT),
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        DeviceClass.SIGNAL_STRENGTH,
        Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ): SensorEntityDescription(
        key=f"{DeviceClass.SIGNAL_STRENGTH}_{Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # Used for e.g. moisture sensor on HHCCJCY01
    (None, Units.PERCENTAGE): SensorEntityDescription(
        key=str(Units.PERCENTAGE),
        device_class=None,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Used for e.g. conductivity sensor on HHCCJCY01
    (None, Units.CONDUCTIVITY): SensorEntityDescription(
        key=str(Units.CONDUCTIVITY),
        device_class=None,
        native_unit_of_measurement=CONDUCTIVITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Used for e.g. formaldehyde
    (None, Units.CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER): SensorEntityDescription(
        key=str(Units.CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER),
        native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


def _device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)


def _sensor_device_info_to_hass(
    sensor_device_info: SensorDeviceInfo,
) -> DeviceInfo:
    """Convert a sensor device info to a sensor device info."""
    hass_device_info = DeviceInfo({})
    if sensor_device_info.name is not None:
        hass_device_info[ATTR_NAME] = sensor_device_info.name
    if sensor_device_info.manufacturer is not None:
        hass_device_info[ATTR_MANUFACTURER] = sensor_device_info.manufacturer
    if sensor_device_info.model is not None:
        hass_device_info[ATTR_MODEL] = sensor_device_info.model
    return hass_device_info


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: _sensor_device_info_to_hass(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            _device_key_to_bluetooth_entity_key(device_key): SENSOR_DESCRIPTIONS[
                (description.device_class, description.native_unit_of_measurement)
            ]
            for device_key, description in sensor_update.entity_descriptions.items()
            if description.native_unit_of_measurement
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


def process_service_info(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    data: XiaomiBluetoothDeviceData,
    service_info: BluetoothServiceInfoBleak,
) -> PassiveBluetoothDataUpdate:
    """Process a BluetoothServiceInfoBleak, running side effects and returning sensor data."""
    update = data.update(service_info)

    # If device isn't pending we know it has seen at least one broadcast with a payload
    # If that payload was encrypted and the bindkey was not verified then we need to reauth
    if (
        not data.pending
        and data.encryption_scheme != EncryptionScheme.NONE
        and not data.bindkey_verified
    ):
        entry.async_start_reauth(hass, data={"device": data})

    return sensor_update_to_bluetooth_data_update(update)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Xiaomi BLE sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    kwargs = {}
    if bindkey := entry.data.get("bindkey"):
        kwargs["bindkey"] = bytes.fromhex(bindkey)
    data = XiaomiBluetoothDeviceData(**kwargs)
    processor = PassiveBluetoothDataProcessor(
        lambda service_info: process_service_info(hass, entry, data, service_info)
    )
    entry.async_on_unload(
        processor.async_add_entities_listener(
            XiaomiBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class XiaomiBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[Optional[Union[float, int]]]
    ],
    SensorEntity,
):
    """Representation of a xiaomi ble sensor."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
