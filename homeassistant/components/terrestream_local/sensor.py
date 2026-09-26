"""Local readings with acquisition-based expiry."""

from collections.abc import Callable
from datetime import datetime
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .coordinator import TerrestreamConfigEntry, TerrestreamCoordinator as Coordinator
from .entity import Entity

PARALLEL_UPDATES = 0

SENSORS: dict[str, tuple[str, SensorDeviceClass | None, str | None]] = {
    "co2": ("Carbon dioxide", SensorDeviceClass.CO2, "ppm"),
    "pm1": ("PM1", SensorDeviceClass.PM1, "µg/m³"),
    "pm25": ("PM2.5", SensorDeviceClass.PM25, "µg/m³"),
    "pm4": ("PM4", None, "µg/m³"),
    "pm10": ("PM10", SensorDeviceClass.PM10, "µg/m³"),
    "temperature": ("Temperature", SensorDeviceClass.TEMPERATURE, "°C"),
    "humidity": ("Humidity", SensorDeviceClass.HUMIDITY, "%"),
    "pressure": ("Pressure", SensorDeviceClass.ATMOSPHERIC_PRESSURE, "hPa"),
    "illuminance": ("Illuminance", SensorDeviceClass.ILLUMINANCE, "lx"),
    "computed_epa_aqi": ("Computed EPA particulate AQI", SensorDeviceClass.AQI, None),
    "voc_index": ("VOC index", None, None),
    "nox_index": ("NOx index", None, None),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerrestreamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the supported measurement entities."""
    async_add_entities(
        [
            Sensor(entry.runtime_data, key, *description)
            for key, description in SENSORS.items()
        ]
    )


class Sensor(Entity, SensorEntity):
    """Expose one measurement until its acquisition deadline."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: Coordinator,
        key: str,
        name: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
    ) -> None:
        """Initialize measurement metadata and its expiry timer."""
        super().__init__(coordinator, key, name)
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._cancel_expiry: Callable[[], None] | None = None

    @callback
    def _schedule_expiry(self) -> None:
        if self._cancel_expiry:
            self._cancel_expiry()
            self._cancel_expiry = None
        remaining = self.coordinator.client.measurement_remaining(self.key)
        if remaining > 0:
            self._cancel_expiry = async_call_later(self.hass, remaining, self._expire)

    @callback
    def _expire(self, _now: datetime) -> None:
        self._cancel_expiry = None
        self.async_write_ha_state()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self._schedule_expiry()
        super()._handle_coordinator_update()

    @override
    async def async_added_to_hass(self) -> None:
        """Schedule expiry after the entity is registered."""
        await super().async_added_to_hass()
        self._schedule_expiry()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel expiry before removing the entity."""
        if self._cancel_expiry:
            self._cancel_expiry()
        await super().async_will_remove_from_hass()

    @property
    @override
    def available(self) -> bool:
        """Require both a successful poll and a fresh measurement."""
        return super().available and self.coordinator.client.measurement_available(
            self.key
        )

    @property
    @override
    def native_value(self) -> float | int | None:
        """Return the fresh measurement, without substituting missing values."""
        return (
            self.coordinator.data["measurements"][self.key].get("value")
            if self.available
            else None
        )
