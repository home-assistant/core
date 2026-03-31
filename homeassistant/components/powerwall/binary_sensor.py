"""Support for powerwall binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PowerwallConfigEntry, PowerwallRuntimeData
from .entity import PowerWallEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerwallConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the powerwall binary sensors."""
    powerwall_data = entry.runtime_data

    async_add_entities(
        [
            PowerWallGridStatusSensor(powerwall_data),
            PowerWallChargingStatusSensor(powerwall_data),
            PowerWallGridServicesActiveSensor(powerwall_data),
        ]
    )


class PowerWallGridStatusSensor(PowerWallEntity, BinarySensorEntity):
    """Representation of a Powerwall grid status sensor."""

    _attr_translation_key = "grid_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, powerwall_data: PowerwallRuntimeData) -> None:
        """Initialize the sensor."""
        super().__init__(powerwall_data)
        self._attr_unique_id = f"{self.base_unique_id}_grid_connected"

    @property
    def is_on(self) -> bool:
        """Return True if grid is connected."""
        return self.data.grid_status == "UP"


class PowerWallChargingStatusSensor(PowerWallEntity, BinarySensorEntity):
    """Representation of a Powerwall charging status sensor."""

    _attr_translation_key = "battery_charging"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, powerwall_data: PowerwallRuntimeData) -> None:
        """Initialize the sensor."""
        super().__init__(powerwall_data)
        self._attr_unique_id = f"{self.base_unique_id}_battery_charging"

    @property
    def is_on(self) -> bool:
        """Return True if battery is charging."""
        # Negative power means charging
        return self.data.battery.instant_power < 0


class PowerWallGridServicesActiveSensor(PowerWallEntity, BinarySensorEntity):
    """Representation of a Powerwall grid services active sensor."""

    _attr_translation_key = "grid_services_active"
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, powerwall_data: PowerwallRuntimeData) -> None:
        """Initialize the sensor."""
        super().__init__(powerwall_data)
        self._attr_unique_id = f"{self.base_unique_id}_grid_services_active"

    @property
    def is_on(self) -> bool:
        """Return True if grid services are active."""
        return self.data.grid_services_active
