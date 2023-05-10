"""Platform for beewi_smartclim integration."""

from __future__ import annotations

from bleak.backends.device import BLEDevice
from smartclim_ble import BeeWiSmartClimAdvertisement

from homeassistant import config_entries
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
from homeassistant.const import ATTR_NAME, PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DEVICE_CLASS_NAME, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    "temperature": SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "battery": SensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "interval": SensorEntityDescription(
        key="update_interval",
        name="Update Interval",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        # The interval setting is not a generally useful entity for most users.
        entity_registry_enabled_default=False,
    ),
}


def _device_key_to_bluetooth_entity_key(
    device: BLEDevice,
    key: str,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(key, device.address)


def _sensor_device_info_to_hass(
    adv: BeeWiSmartClimAdvertisement,
) -> DeviceInfo:
    """Convert a sensor device info to hass device info."""
    hass_device_info = DeviceInfo({})
    if adv.readings and adv.readings.name:
        hass_device_info[ATTR_NAME] = adv.readings.name
    return hass_device_info


def sensor_update_to_bluetooth_data_update(
    adv: BeeWiSmartClimAdvertisement,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a Bluetooth data update."""
    entity_names: dict[PassiveBluetoothEntityKey, str | None] = {}
    for key, desc in SENSOR_DESCRIPTIONS.items():
        # PassiveBluetoothDataUpdate does not support DEVICE_CLASS_NAME
        # the assert satisfies the type checker and will catch attempts
        # to use DEVICE_CLASS_NAME in the entity descriptions.
        assert desc.name is not DEVICE_CLASS_NAME
        entity_names[_device_key_to_bluetooth_entity_key(adv.device, key)] = desc.name

    return PassiveBluetoothDataUpdate(
        devices={adv.device.address: _sensor_device_info_to_hass(adv)},
        entity_descriptions={
            _device_key_to_bluetooth_entity_key(adv.device, key): desc
            for key, desc in SENSOR_DESCRIPTIONS.items()
        },
        entity_data={
            _device_key_to_bluetooth_entity_key(adv.device, key): getattr(
                adv.readings, key, None
            )
            for key in SENSOR_DESCRIPTIONS
        },
        entity_names=entity_names,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BeeWi SmartClim BLE sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]

    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            BeeWiSmartClimBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class BeeWiSmartClimBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity, SensorEntity
):
    """Representation of an BeeWi SmartClim BLE sensor."""

    @property
    def native_value(self) -> float | int | str | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
