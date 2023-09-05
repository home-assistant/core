"""Support for iBeacon device sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from bluetooth_data_tools import calculate_distance_meters

from homeassistant.components import bluetooth
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BasePrivateDeviceEntity


@dataclass
class PrivateDeviceSensorEntityDescriptionRequired:
    """Required domain specific fields for sensor entity."""

    value_fn: Callable[[bluetooth.BluetoothServiceInfoBleak], str | int | float | None]


@dataclass
class PrivateDeviceSensorEntityDescription(
    SensorEntityDescription, PrivateDeviceSensorEntityDescriptionRequired
):
    """Describes sensor entity."""


SENSOR_DESCRIPTIONS = (
    PrivateDeviceSensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda service_info: service_info.advertisement.rssi,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PrivateDeviceSensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda service_info: service_info.advertisement.tx_power,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PrivateDeviceSensorEntityDescription(
        key="estimated_distance",
        translation_key="estimated_distance",
        icon="mdi:signal-distance-variant",
        native_unit_of_measurement=UnitOfLength.METERS,
        value_fn=lambda service_info: service_info.advertisement
        and service_info.advertisement.tx_power
        and calculate_distance_meters(
            service_info.advertisement.tx_power * 10, service_info.advertisement.rssi
        ),
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors for Private BLE component."""
    async_add_entities(
        PrivateBLEDeviceSensor(entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class PrivateBLEDeviceSensor(BasePrivateDeviceEntity, SensorEntity):
    """A sensor entity."""

    entity_description: PrivateDeviceSensorEntityDescription

    def __init__(
        self,
        config_entry: ConfigEntry,
        entity_description: PrivateDeviceSensorEntityDescription,
    ) -> None:
        """Initialize an sensor entity."""
        self.entity_description = entity_description
        self._attr_available = False
        super().__init__(config_entry)

    @callback
    def _async_track_service_info(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update state."""
        self._attr_available = True
        self._last_info = service_info
        self.async_write_ha_state()

    @callback
    def _async_track_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Update state."""
        self._attr_available = False
        self.async_write_ha_state()

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        assert self._last_info
        return self.entity_description.value_fn(self._last_info)
