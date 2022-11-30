"""Support for Aranet sensors."""
from __future__ import annotations

from typing import Optional, Union

from aranet4.client import Aranet4Advertisement
from bleak.backends.device import BLEDevice

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
from homeassistant.const import (
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    PRESSURE_HPA,
    TEMP_CELSIUS,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

SENSOR_DESCRIPTIONS = {
    "temperature": SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pressure": SensorEntityDescription(
        key="pressure",
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "co2": SensorEntityDescription(
        key="co2",
        name="Carbon Dioxide",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
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
        native_unit_of_measurement=TIME_SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


def _device_key_to_bluetooth_entity_key(
    device: BLEDevice,
    key: str,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(key, device.address)


def _sensor_device_info_to_hass(
    adv: Aranet4Advertisement,
) -> DeviceInfo:
    """Convert a sensor device info to hass device info."""
    hass_device_info = DeviceInfo({})
    if adv.readings and adv.readings.name:
        hass_device_info[ATTR_NAME] = adv.readings.name
    if adv.manufacturer_data:
        hass_device_info[ATTR_SW_VERSION] = str(adv.manufacturer_data.version)
    return hass_device_info


def sensor_update_to_bluetooth_data_update(
    adv: Aranet4Advertisement,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a Bluetooth data update."""
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
        entity_names={
            _device_key_to_bluetooth_entity_key(adv.device, key): desc.name
            for key, desc in SENSOR_DESCRIPTIONS.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aranet sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            Aranet4BluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class Aranet4BluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[Optional[Union[float, int]]]
    ],
    SensorEntity,
):
    """Representation of an Aranet sensor."""

    @property
    def available(self) -> bool:
        """Return whether the entity was available in the last update."""
        # Our superclass covers "did the device disappear entirely", but if the
        # device has smart home integrations disabled, it will send BLE beacons
        # without data, which we turn into Nones here. Because None is never a
        # valid value for any of the Aranet sensors, that means the entity is
        # actually unavailable.
        return (
            super().available
            and self.processor.entity_data.get(self.entity_key) is not None
        )

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
