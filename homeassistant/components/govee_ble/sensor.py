"""Support for govee ble sensors."""
from __future__ import annotations

from typing import Optional, Union

from govee_ble import DeviceClass, Units

from homeassistant import config_entries
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
    PassiveBluetoothDataUpdateCoordinator,
    PassiveBluetoothEntityKey,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
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
    (DeviceClass.BATTERY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{DeviceClass.BATTERY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
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
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Govee BLE sensors."""
    coordinator: PassiveBluetoothDataUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]

    def _entities_filter(
        entity_key: PassiveBluetoothEntityKey, description: EntityDescription
    ) -> bool:
        """Check if the entity should be added to this platform."""
        return isinstance(description, SensorEntityDescription)

    entry.async_on_unload(
        coordinator.async_add_entities_listener(
            GoveeBluetoothSensorEntity, async_add_entities, _entities_filter
        )
    )


class GoveeBluetoothSensorEntity(
    PassiveBluetoothCoordinatorEntity[
        PassiveBluetoothDataUpdateCoordinator[Optional[Union[float, int]]]
    ],
    SensorEntity,
):
    """Representation of a govee ble sensor."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.coordinator.entity_data.get(self.entity_key)
