"""Support for Transport NSW (AU) to query next leave event."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MODE, CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DELAY,
    ATTR_DESTINATION,
    ATTR_DUE_IN,
    ATTR_REAL_TIME,
    ATTR_ROUTE,
    ATTR_STOP_ID,
    CONF_STOP_ID,
    DOMAIN,
    TRANSPORT_ICONS,
)
from .coordinator import TransportNSWCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Transport NSW sensor from a config entry."""
    coordinator = TransportNSWCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([TransportNSWSensor(coordinator, config_entry)], True)



class TransportNSWSensor(CoordinatorEntity, SensorEntity):
    """Implementation of an Transport NSW sensor."""

    _attr_attribution = "Data provided by Transport NSW"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(
        self, coordinator: TransportNSWCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_name = config_entry.data[CONF_NAME]
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}"

        # Device info for grouping entities
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.data[CONF_STOP_ID])},
            name=f"Transport NSW Stop {config_entry.data[CONF_STOP_ID]}",
            manufacturer="Transport NSW",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(ATTR_DUE_IN)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self.coordinator.data is None:
            return None

        return {
            ATTR_STOP_ID: self.config_entry.data[CONF_STOP_ID],
            ATTR_ROUTE: self.coordinator.data.get(ATTR_ROUTE),
            ATTR_DELAY: self.coordinator.data.get(ATTR_DELAY),
            ATTR_REAL_TIME: self.coordinator.data.get(ATTR_REAL_TIME),
            ATTR_DESTINATION: self.coordinator.data.get(ATTR_DESTINATION),
            ATTR_MODE: self.coordinator.data.get(ATTR_MODE),
        }

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        if self.coordinator.data is None:
            return TRANSPORT_ICONS[None]
        mode = self.coordinator.data.get(ATTR_MODE)
        return TRANSPORT_ICONS.get(mode, TRANSPORT_ICONS[None])
