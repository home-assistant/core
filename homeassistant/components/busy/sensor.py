"""Battery and Wi-Fi sensors for BUSY Bar."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from busylib.types import WifiState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BusyConfigEntry, BusyData
from .entity import BusyEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BusySensorEntityDescription(SensorEntityDescription):
    """Describe a BUSY Bar sensor."""

    value_fn: Callable[[BusyData], int | str | None]


SENSORS = (
    BusySensorEntityDescription(
        key="battery",
        value_fn=lambda d: d.status.power.battery_charge if d.status.power else None,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BusySensorEntityDescription(
        key="wifi_signal",
        value_fn=lambda d: d.wifi.rssi if d.wifi.state == WifiState.CONNECTED else None,
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BusySensorEntityDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        value_fn=lambda d: d.wifi.ssid if d.wifi.state == WifiState.CONNECTED else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BusyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BUSY Bar sensors."""
    async_add_entities(
        BusySensor(entry.runtime_data, description) for description in SENSORS
    )


class BusySensor(BusyEntity, SensorEntity):
    """One value from the bar's last successful poll."""

    entity_description: BusySensorEntityDescription

    @property
    @override
    def native_value(self) -> int | str | None:
        """Return the reading from the last poll."""
        return self.entity_description.value_fn(self.coordinator.data)
