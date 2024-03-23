"""Support for Dexcom sensors."""

from __future__ import annotations

from pydexcom import GlucoseReading

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, MG_DL

TRENDS = {
    1: "rising_quickly",
    2: "rising",
    3: "rising_slightly",
    4: "steady",
    5: "falling_slightly",
    6: "falling",
    7: "falling_quickly",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Dexcom sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    username = config_entry.data[CONF_USERNAME]
    unit_of_measurement = config_entry.options[CONF_UNIT_OF_MEASUREMENT]
    async_add_entities(
        [
            DexcomGlucoseTrendSensor(coordinator, username, config_entry.entry_id),
            DexcomGlucoseValueSensor(
                coordinator, username, config_entry.entry_id, unit_of_measurement
            ),
        ],
    )


class DexcomSensorEntity(
    CoordinatorEntity[DataUpdateCoordinator[GlucoseReading]], SensorEntity
):
    """Base Dexcom sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[GlucoseReading],
        username: str,
        entry_id: str,
        key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{username}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=username,
        )


class DexcomGlucoseValueSensor(DexcomSensorEntity):
    """Representation of a Dexcom glucose value sensor."""

    _attr_translation_key = "glucose_value"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        username: str,
        entry_id: str,
        unit_of_measurement: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, username, entry_id, "value")
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._key = "mg_dl" if unit_of_measurement == MG_DL else "mmol_l"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            return getattr(self.coordinator.data, self._key)
        return None


class DexcomGlucoseTrendSensor(DexcomSensorEntity):
    """Representation of a Dexcom glucose trend sensor."""

    _attr_translation_key = "glucose_trend"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(TRENDS.values())

    def __init__(
        self, coordinator: DataUpdateCoordinator, username: str, entry_id: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, username, entry_id, "trend")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return TRENDS.get(self.coordinator.data.trend)
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and (
            self.coordinator.data is None or self.coordinator.data.trend != 9
        )
