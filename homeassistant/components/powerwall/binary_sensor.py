"""Support for powerwall binary sensors."""

from typing import TYPE_CHECKING

from tesla_powerwall import GridStatus, MeterType

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import PowerWallEntity
from .models import PowerwallConfigEntry

CONNECTED_GRID_STATUSES = {
    GridStatus.TRANSITION_TO_GRID,
    GridStatus.CONNECTED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerwallConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the powerwall sensors."""
    powerwall_data = entry.runtime_data
    async_add_entities(
        [
            sensor_class(powerwall_data)
            for sensor_class in (
                PowerWallRunningSensor,
                PowerWallGridServicesActiveSensor,
                PowerWallGridStatusSensor,
                PowerWallConnectedSensor,
                PowerWallChargingStatusSensor,
            )
        ]
    )


class PowerWallRunningSensor(PowerWallEntity, BinarySensorEntity):
    """Representation of an Powerwall running sensor."""

    _attr_translation_key = "status"
    _attr_device_class = BinarySensorDeviceClass.POWER

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_running"

    @property
    def is_on(self) -> bool:
        """Get the powerwall running state."""
        return self.data.site_master.is_running


class PowerWallConnectedSensor(PowerWallEntity, BinarySensorEntity):
    """Representation of an Powerwall connected sensor."""

    _attr_translation_key = "connected_to_tesla"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_connected_to_tesla"

    @property
    def is_on(self) -> bool:
        """Get the powerwall connected to tesla state."""
        return self.data.site_master.is_connected_to_tesla


class PowerWallGridServicesActiveSensor(PowerWallEntity, BinarySensorEntity):
    """Representation of a Powerwall grid services active sensor."""

    _attr_translation_key = "grid_services_active"
    _attr_device_class = BinarySensorDeviceClass.POWER

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_grid_services_active"

    @property
    def is_on(self) -> bool:
        """Grid services is active."""
        return self.data.grid_services_active


class PowerWallGridStatusSensor(PowerWallEntity, BinarySensorEntity):
    """Representation of an Powerwall grid status sensor."""

    _attr_translation_key = "grid_status"
    _attr_device_class = BinarySensorDeviceClass.POWER

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_grid_status"

    @property
    def is_on(self) -> bool:
        """Grid is online."""
        return self.data.grid_status in CONNECTED_GRID_STATUSES


class PowerWallChargingStatusSensor(PowerWallEntity, BinarySensorEntity):
    """Representation of an Powerwall charging status sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    @property
    def available(self) -> bool:
        """Powerwall is available."""
        # Return False if no battery is installed
        return (
            super().available
            and self.data.meters.get_meter(MeterType.BATTERY) is not None
        )

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_powerwall_charging"

    @property
    def is_on(self) -> bool:
        """Powerwall is charging."""
        meter = self.data.meters.get_meter(MeterType.BATTERY)
        # Meter cannot be None because of the available property
        if TYPE_CHECKING:
            assert meter is not None
        # is_sending_to returns true for values greater than 100 watts
        return meter.is_sending_to()
