"""Sensors for LIFX lights."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import StateType

from .const import ATTR_RSSI, DOMAIN
from .coordinator import LIFXUpdateCoordinator
from .entity import LIFXEntity

SCAN_INTERVAL = timedelta(seconds=30)

RSSI_SENSOR = SensorEntityDescription(
    key=ATTR_RSSI,
    name="RSSI",
    device_class=SensorDeviceClass.SIGNAL_STRENGTH,
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=SensorStateClass.MEASUREMENT,
    entity_registry_enabled_default=False,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LIFX sensor from config entry."""
    coordinator: LIFXUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LIFXRssiSensor(coordinator, RSSI_SENSOR)])


class LIFXRssiSensor(LIFXEntity, SensorEntity):
    """LIFX RSSI sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, coordinator: LIFXUpdateCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialise the RSSI sensor."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"
        self._attr_native_unit_of_measurement = coordinator.rssi_uom

    @property
    def native_value(self) -> StateType:
        """Return the current RSSI value."""
        return self.coordinator.rssi

    @callback
    async def async_added_to_hass(self) -> None:
        """Get the coordinator to update RSSI every minute."""

        self.async_on_remove(
            async_track_time_interval(
                self.hass, self.coordinator.async_update_rssi, SCAN_INTERVAL
            )
        )
        return await super().async_added_to_hass()
