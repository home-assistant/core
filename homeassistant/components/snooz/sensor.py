"""Support for Snooz device sensors."""
from __future__ import annotations

from collections.abc import Callable
from typing import Optional, Union

from pysnooz.device import SnoozDevice
from sensor_state_data import (
    DeviceClass,
    DeviceKey,
    SensorDeviceInfo,
    SensorUpdate,
    Units,
)

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
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
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .models import SnoozConfigurationData

SENSOR_DESCRIPTIONS = {
    (
        DeviceClass.SIGNAL_STRENGTH,
        Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ): SensorEntityDescription(
        key=f"{DeviceClass.SIGNAL_STRENGTH}_{Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
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
            if description.device_class and description.native_unit_of_measurement
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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Snooz device sensors."""
    config_data: SnoozConfigurationData = hass.data[DOMAIN][entry.entry_id]
    processor = PassiveBluetoothDataProcessor(
        update_method=sensor_update_to_bluetooth_data_update
    )
    async_add_entities(
        [
            SnoozConnectionStatusSensorEntity(config_data.device),
        ]
    )
    entry.async_on_unload(
        processor.async_add_entities_listener(SnoozSensorEntity, async_add_entities)
    )
    entry.async_on_unload(config_data.coordinator.async_register_processor(processor))


class SnoozSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[Optional[Union[float, int]]]
    ],
    SensorEntity,
):
    """Representation of a Snooz device sensor."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)


class SnoozConnectionStatusSensorEntity(SensorEntity):
    """Representation of a Snooz connection status."""

    def __init__(self, device: SnoozDevice) -> None:
        """Initialize a connection status sensor entity."""
        self._device = device
        self._attr_entity_registry_enabled_default = True
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_unique_id = f"{device.address}.connection_status"
        self._attr_name = f"{device.display_name} Connection Status"
        self._attr_should_poll = False

    @property
    def native_value(self) -> str:
        """Lowercase connection status string of the device."""
        return self._device.connection_status.name.lower()

    async def async_added_to_hass(self) -> None:
        """Subscribe to device events."""
        await super().async_added_to_hass()

        self.async_on_remove(self._subscribe_to_device_events())

    def _subscribe_to_device_events(self) -> Callable[[], None]:
        events = self._device.events

        def unsubscribe():
            events.on_connection_status_change -= self._on_connection_status_changed

        events.on_connection_status_change += self._on_connection_status_changed

        return unsubscribe

    def _on_connection_status_changed(self, new_status) -> None:
        self.async_write_ha_state()
