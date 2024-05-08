"""Support for MikroTik BT5 tags."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mikrotik_bt5 import MikrotikBeacon
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
    ATTR_MANUFACTURER,
    ATTR_NAME,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import MIKROTIK_MANUFACTURER_NAME, DOMAIN


@dataclass(frozen=True)
class MikroTikSensorEntityDescription(SensorEntityDescription):
    """Class to describe an MikroTik BT5 sensor entity."""

    # PassiveBluetoothDataUpdate does not support UNDEFINED
    # Restrict the type to satisfy the type checker and catch attempts
    # to use UNDEFINED in the entity descriptions.
    name: str | None = None
    value: float | None = None


SENSOR_DESCRIPTIONS = {
    "temperature": MikroTikSensorEntityDescription(
        key="temperature",
        name="Temperature",
        value=lambda adv: adv.temperature,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "acceleration": MikroTikSensorEntityDescription(
        key="acceleration",
        name="Acceleration",
        value=lambda adv: (
            None if not adv.acceleration else adv.acceleration.magnitude()
        ),
        native_unit_of_measurement="m/s²",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:axis-arrow"
    ),
    "battery": MikroTikSensorEntityDescription(
        key="battery",
        name="Battery",
        value=lambda adv: adv.battery,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "uptime": MikroTikSensorEntityDescription(
        key="uptime",
        name="Uptime",
        value=lambda adv: adv.uptime,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        # The uptime setting is not a generally useful entity for most users
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


def _device_key_to_bluetooth_entity_key(
    addr: str,
    key: str,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(key, addr)


def _sensor_device_info_to_hass(
    adv: MikrotikBeacon,
) -> DeviceInfo:
    """Convert a sensor device info to hass device info."""
    hass_device_info = DeviceInfo({})
    # if adv.valid and adv.readings.name:
    hass_device_info[ATTR_NAME] = "BT5 " + adv.address.upper()
    hass_device_info[ATTR_MANUFACTURER] = MIKROTIK_MANUFACTURER_NAME
    return hass_device_info


def sensor_update_to_bluetooth_data_update(
    adv: MikrotikBeacon,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a Bluetooth data update."""
    data: dict[PassiveBluetoothEntityKey, Any] = {}
    names: dict[PassiveBluetoothEntityKey, str | None] = {}
    descs: dict[PassiveBluetoothEntityKey, EntityDescription] = {}
    for key, desc in SENSOR_DESCRIPTIONS.items():
        tag = _device_key_to_bluetooth_entity_key(adv.address, key)
        v = desc.value(adv)
        if v == None:
            continue
        data[tag] = v
        names[tag] = desc.name
        descs[tag] = desc
    return PassiveBluetoothDataUpdate(
        devices={adv.address: _sensor_device_info_to_hass(adv)},
        entity_descriptions=descs,
        entity_data=data,
        entity_names=names,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MikroTik BT5 tags sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            MikroTikSensorEntityDescription, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class MikroTikSensorEntityDescription(
    PassiveBluetoothProcessorEntity[PassiveBluetoothDataProcessor[float | int | None]],
    SensorEntity,
):
    """Representation of an MikroTik BT5 tag."""

    @property
    def available(self) -> bool:
        """Return whether the entity was available in the last update."""
        return (
            super().available
            and self.processor.entity_data.get(self.entity_key) is not None
        )

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
