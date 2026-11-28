"""Battery sensors for Flic buttons."""

from itertools import pairwise
from math import isfinite
from typing import override

from pyflic_ble import DeviceType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlicButtonConfigEntry, FlicButtonData
from .entity import FlicButtonEntity

PARALLEL_UPDATES = 0

BATTERY_VOLTAGE = SensorEntityDescription(
    key="battery_voltage",
    translation_key="battery_voltage",
    device_class=SensorDeviceClass.VOLTAGE,
    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    suggested_display_precision=2,
)
BATTERY_LEVEL = SensorEntityDescription(
    key="battery_level",
    translation_key="battery_level",
    device_class=SensorDeviceClass.BATTERY,
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    suggested_display_precision=0,
)

# Estimated Flic 2 capacity from Shortcut Labs' Android SDK BatteryLevel.java.
# https://github.com/50ButtonsEach/flic2lib-android/blob/master/
# flic2lib-android/src/main/java/io/flic/flic2libandroid/BatteryLevel.java
_BATTERY_CURVE = ((2100, 0), (2440, 6), (2740, 18), (2900, 42), (3000, 100))


def _estimate_battery_percentage(voltage: float | None) -> int | None:
    """Apply the manufacturer's Flic 2 voltage-to-capacity estimate."""
    if voltage is None or not isfinite(voltage):
        return None
    millivolts = int(voltage * 1000)
    if millivolts <= _BATTERY_CURVE[0][0]:
        return 0
    for (low_mv, low_pct), (high_mv, high_pct) in pairwise(_BATTERY_CURVE):
        if millivolts < high_mv:
            return low_pct + (millivolts - low_mv) * (high_pct - low_pct) // (
                high_mv - low_mv
            )
    return 100


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlicButtonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up battery sensors from the client's cached state."""
    data = entry.runtime_data
    entities: list[FlicBatterySensor] = [FlicBatterySensor(data, BATTERY_VOLTAGE)]
    if data.client.device_type is DeviceType.FLIC2:
        entities.append(FlicBatteryLevelSensor(data, BATTERY_LEVEL))
    async_add_entities(entities)


class FlicBatterySensor(FlicButtonEntity, SensorEntity):
    """Battery voltage last read by the existing connection lifecycle."""

    def __init__(
        self, data: FlicButtonData, description: SensorEntityDescription
    ) -> None:
        """Initialize a battery sensor."""
        super().__init__(data)
        self.entity_description = description
        self._attr_unique_id = f"{self._client.address}-{description.key}"

    @property
    @override
    def available(self) -> bool:
        """Retain cached measurements when a button disconnects."""
        return True

    @property
    @override
    def native_value(self) -> float | None:
        """Return the last known voltage without querying the device."""
        voltage = self._client.state.battery_voltage
        return voltage if voltage is not None and isfinite(voltage) else None


class FlicBatteryLevelSensor(FlicBatterySensor):
    """Estimated Flic 2 battery capacity."""

    @property
    @override
    def native_value(self) -> int | None:
        """Return the estimated remaining capacity."""
        return _estimate_battery_percentage(self._client.state.battery_voltage)
