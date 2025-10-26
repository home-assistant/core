"""Sensor for PG LAB Electronics."""

from __future__ import annotations

from pypglab.const import SENSOR_REBOOT_TIME, SENSOR_TEMPERATURE, SENSOR_VOLTAGE
from pypglab.device import Device as PyPGLabDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import Platform, UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PGLabConfigEntry
from .coordinator import PGLabSensorsCoordinator
from .discovery import PGLabDiscovery
from .entity import PGLabSensorEntity

PARALLEL_UPDATES = 0

SENSOR_INFO: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=SENSOR_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_VOLTAGE,
        translation_key="mpu_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_REBOOT_TIME,
        translation_key="runtime",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:progress-clock",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PGLabConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor for device."""

    @callback
    def async_discover(
        pglab_device: PyPGLabDevice,
        pglab_coordinator: PGLabSensorsCoordinator,
    ) -> None:
        """Discover and add a PG LAB Sensor."""
        pglab_discovery = config_entry.runtime_data

        sensors: list[PGLabSensor] = [
            PGLabSensor(
                description,
                pglab_discovery,
                pglab_device,
                pglab_coordinator,
            )
            for description in SENSOR_INFO
        ]

        async_add_entities(sensors)

    # Register the callback to create the sensor entity when discovered.
    pglab_discovery = config_entry.runtime_data
    await pglab_discovery.register_platform(hass, Platform.SENSOR, async_discover)


class PGLabSensor(PGLabSensorEntity, SensorEntity):
    """A PGLab sensor."""

    def __init__(
        self,
        description: SensorEntityDescription,
        pglab_discovery: PGLabDiscovery,
        pglab_device: PyPGLabDevice,
        pglab_coordinator: PGLabSensorsCoordinator,
    ) -> None:
        """Initialize the Sensor class."""

        super().__init__(pglab_discovery, pglab_device, pglab_coordinator)

        self._attr_unique_id = f"{pglab_device.id}_{description.key}"
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""

        self._attr_native_value = self.coordinator.get_sensor_value(
            self.entity_description.key
        )
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return PG LAB sensor availability."""
        return super().available and self.native_value is not None
