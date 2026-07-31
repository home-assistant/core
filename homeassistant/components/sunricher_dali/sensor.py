"""Platform for Sunricher DALI sensor entities."""

import logging
from typing import override

from PySrDaliGateway import CallbackEventType, Device
from PySrDaliGateway.helper import is_illuminance_sensor, is_light_device
from PySrDaliGateway.types import IlluminanceStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import LIGHT_LUX, EntityCategory, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import DaliDeviceEntity
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sunricher DALI sensor entities from config entry."""
    devices = entry.runtime_data.devices

    entities: list[SensorEntity] = []
    for device in devices:
        if is_illuminance_sensor(device.dev_type):
            entities.append(SunricherDaliIlluminanceSensor(hass, device, entry))
        if is_light_device(device.dev_type):
            entities.append(SunricherDaliEnergySensor(hass, device, entry))

    if entities:
        async_add_entities(entities)


class SunricherDaliIlluminanceSensor(DaliDeviceEntity, SensorEntity):
    """Representation of a Sunricher DALI Illuminance Sensor."""

    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = LIGHT_LUX
    _attr_name = None

    def __init__(
        self, hass: HomeAssistant, device: Device, entry: DaliCenterConfigEntry
    ) -> None:
        """Initialize the illuminance sensor."""
        super().__init__(hass, device, entry)
        self._illuminance_value: float | None = None
        self._sensor_enabled: bool = True

    @property
    @override
    def native_value(self) -> float | None:
        """Return the native value, or None if sensor is disabled."""
        if not self._sensor_enabled:
            return None
        return self._illuminance_value

    @override
    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._device.register_listener(
                CallbackEventType.ILLUMINANCE_STATUS, self._handle_illuminance_status
            )
        )

        self.async_on_remove(
            self._device.register_listener(
                CallbackEventType.SENSOR_ON_OFF, self._handle_sensor_on_off
            )
        )

        self._device.read_status()

    @callback
    def _handle_illuminance_status(self, status: IlluminanceStatus) -> None:
        """Handle illuminance status updates."""
        illuminance_value = status["illuminance_value"]
        is_valid = status["is_valid"]

        if not is_valid:
            _LOGGER.debug(
                "Illuminance value is not valid for device %s: %s lux",
                self._device.dev_id,
                illuminance_value,
            )
            return

        self._illuminance_value = illuminance_value
        self.schedule_update_ha_state()

    @callback
    def _handle_sensor_on_off(self, on_off: bool) -> None:
        """Handle sensor on/off updates."""
        self._sensor_enabled = on_off
        _LOGGER.debug(
            "Illuminance sensor enable state for device %s updated to: %s",
            self._device.dev_id,
            on_off,
        )
        self.schedule_update_ha_state()


class SunricherDaliEnergySensor(DaliDeviceEntity, SensorEntity):
    """Representation of a Sunricher DALI Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 2

    def __init__(
        self, hass: HomeAssistant, device: Device, entry: DaliCenterConfigEntry
    ) -> None:
        """Initialize the energy sensor."""
        super().__init__(hass, device, entry)
        self._attr_unique_id = f"{device.unique_id}_energy"

    @override
    async def async_added_to_hass(self) -> None:
        """Register energy report listener."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._device.register_listener(
                CallbackEventType.ENERGY_REPORT, self._handle_energy_update
            )
        )

    @callback
    def _handle_energy_update(self, energy_value: float) -> None:
        """Update energy value."""
        self._attr_native_value = energy_value
        self.schedule_update_ha_state()
