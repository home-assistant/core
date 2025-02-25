"""Support for Tilt Hydrometer sensors."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TiltPiDataUpdateCoordinator
from .model import TiltHydrometerData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tilt Hydrometer sensors."""
    coordinator: TiltPiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [TiltTemperatureSensor(coordinator, data) for data in coordinator.data]
        + [TiltGravitySensor(coordinator, data) for data in coordinator.data]
    )


class TiltSensorBase(CoordinatorEntity[TiltPiDataUpdateCoordinator], SensorEntity):
    """Base sensor for Tilt Hydrometer."""

    def __init__(
        self,
        coordinator: TiltPiDataUpdateCoordinator,
        description: SensorEntityDescription,
        hydrometer: TiltHydrometerData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._hydrometer = hydrometer
        self._mac_id = hydrometer.mac_id
        self._attr_unique_id = f"{hydrometer.mac_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hydrometer.mac_id)},
            name=f"Tilt {hydrometer.color}",
            manufacturer="Tilt Hydrometer",
            model=f"{hydrometer.color} Tilt Hydrometer",
        )
        self._attr_has_entity_name = True

    def _get_current_hydrometer(self) -> TiltHydrometerData | None:
        """Get current hydrometer data."""
        if not self.coordinator.data:
            return None
        return next(
            (h for h in self.coordinator.data if h.mac_id == self._mac_id),
            None,
        )


class TiltTemperatureSensor(TiltSensorBase):
    """Temperature sensor for Tilt Hydrometer."""

    def __init__(
        self,
        coordinator: TiltPiDataUpdateCoordinator,
        hydrometer: TiltHydrometerData,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(
            coordinator,
            SensorEntityDescription(
                key="temperature",
                name="Temperature",
                native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            hydrometer,
        )

    @property
    def native_value(self) -> float | None:
        """Return the temperature."""
        if hydrometer := self._get_current_hydrometer():
            return hydrometer.temperature
        return None


class TiltGravitySensor(TiltSensorBase):
    """Specific gravity sensor for Tilt Hydrometer."""

    def __init__(
        self,
        coordinator: TiltPiDataUpdateCoordinator,
        hydrometer: TiltHydrometerData,
    ) -> None:
        """Initialize the gravity sensor."""
        super().__init__(
            coordinator,
            SensorEntityDescription(
                key="gravity",
                name="Specific Gravity",
                native_unit_of_measurement="SG",
                icon="mdi:water",
                state_class=SensorStateClass.MEASUREMENT,
            ),
            hydrometer,
        )

    @property
    def native_value(self) -> float | None:
        """Return the specific gravity."""
        if hydrometer := self._get_current_hydrometer():
            return hydrometer.gravity
        return None
