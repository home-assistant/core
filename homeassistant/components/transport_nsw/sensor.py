"""Support for Transport NSW (AU) to query next leave event."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
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
    CONF_DESTINATION,
    CONF_ROUTE,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
    TRANSPORT_ICONS,
)
from .coordinator import TransportNSWCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Transport NSW sensor from a config entry."""

    # Handle legacy entries (migrate if needed)
    if CONF_STOP_ID in config_entry.data:
        # Legacy entry - create single sensor
        coordinator = TransportNSWCoordinator(hass, config_entry, None)
        await coordinator.async_config_entry_first_refresh()
        async_add_entities([TransportNSWSensor(coordinator, config_entry, None)], True)
        return

    # New subentry-based setup
    sensors = []
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_TYPE_STOP:
            coordinator = TransportNSWCoordinator(hass, config_entry, subentry)
            await coordinator.async_config_entry_first_refresh()
            sensors.append(TransportNSWSensor(coordinator, config_entry, subentry))

    async_add_entities(sensors, True)


class TransportNSWSensor(CoordinatorEntity, SensorEntity):
    """Implementation of an Transport NSW sensor."""

    _attr_attribution = "Data provided by Transport NSW"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(
        self,
        coordinator: TransportNSWCoordinator,
        config_entry: ConfigEntry,
        subentry: ConfigSubentry | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.subentry = subentry

        if subentry:
            # New subentry mode - don't set _attr_name here, use dynamic property
            # Build unique ID with route and destination for better differentiation
            unique_id_parts = [
                DOMAIN,
                config_entry.entry_id,
                subentry.data[CONF_STOP_ID],
            ]

            # Add route if present and not empty
            route = subentry.data.get(CONF_ROUTE, "").strip()
            if route:
                unique_id_parts.append(f"route_{route}")

            # Add destination if present and not empty
            destination = subentry.data.get(CONF_DESTINATION, "").strip()
            if destination:
                unique_id_parts.append(f"dest_{destination}")

            self._attr_unique_id = "_".join(unique_id_parts)
        else:
            # Legacy mode - don't set _attr_name here, use dynamic property
            self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}"

        # Device info for grouping entities - all sensors for same API key group together
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="Transport NSW",
            manufacturer="Transport NSW",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor (dynamically updateable)."""
        if self.subentry:
            # Check if name is provided in subentry data
            custom_name = self.subentry.data.get(CONF_NAME, "").strip()
            if custom_name:
                return custom_name

            # Fall back to subentry title or default pattern
            if self.subentry.title and self.subentry.title.strip():
                return self.subentry.title

            # Generate descriptive name from stop ID, route, and destination
            name_parts = [f"Stop {self.subentry.data[CONF_STOP_ID]}"]

            route = self.subentry.data.get(CONF_ROUTE, "").strip()
            if route:
                name_parts.append(f"Route {route}")

            destination = self.subentry.data.get(CONF_DESTINATION, "").strip()
            if destination:
                name_parts.append(f"to {destination}")

            return " ".join(name_parts)
        # Legacy mode - get name from config entry data
        return self.config_entry.data.get(CONF_NAME, "Transport NSW Stop")

    async def async_update_config(
        self, config_entry: ConfigEntry, subentry: ConfigSubentry | None = None
    ) -> None:
        """Update sensor configuration and refresh coordinator."""
        self.config_entry = config_entry
        self.subentry = subentry

        # Update the coordinator with new configuration
        # Type checking: coordinator is guaranteed to be TransportNSWCoordinator
        coordinator = self.coordinator
        if hasattr(coordinator, "async_update_config"):
            await coordinator.async_update_config(config_entry, subentry)

        # Trigger entity state update to reflect new name/configuration
        self.async_write_ha_state()

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

        if self.subentry:
            stop_id = self.subentry.data[CONF_STOP_ID]
        else:
            stop_id = self.config_entry.data[CONF_STOP_ID]

        return {
            ATTR_STOP_ID: stop_id,
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
