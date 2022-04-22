"""GeoJSON events status sensor."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt

from . import GeoJsonEventsFeedEntityCoordinator
from ...helpers.device_registry import DeviceEntryType
from ...helpers.entity import DeviceInfo, EntityCategory
from ...helpers.update_coordinator import CoordinatorEntity
from .const import (
    ATTR_CREATED,
    ATTR_LAST_TIMESTAMP,
    ATTR_LAST_UPDATE,
    ATTR_LAST_UPDATE_SUCCESSFUL,
    ATTR_REMOVED,
    ATTR_STATUS,
    ATTR_UPDATED,
    DEFAULT_FORCE_UPDATE,
    DEFAULT_UNIT_OF_MEASUREMENT,
    DOMAIN,
    FEED,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the GeoJSON events sensor platform."""
    coordinator = hass.data[DOMAIN][FEED][config_entry.entry_id]
    config_entry_unique_id = config_entry.unique_id

    async_add_entities(
        [GeoJsonEventsSensor(coordinator, config_entry_unique_id)],
        True,
    )
    _LOGGER.debug("Sensor setup done")


class GeoJsonEventsSensor(CoordinatorEntity, SensorEntity):
    """Implementation of the sensor."""

    coordinator: GeoJsonEventsFeedEntityCoordinator
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_force_update = DEFAULT_FORCE_UPDATE
    _attr_native_unit_of_measurement = DEFAULT_UNIT_OF_MEASUREMENT
    _attr_icon = "mdi:information"

    def __init__(
        self,
        coordinator: GeoJsonEventsFeedEntityCoordinator,
        config_entry_unique_id: str | None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry_unique_id}_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="GeoJSON Events",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.url,
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self._update_internal_state()

    def _update_internal_state(self) -> None:
        """Update state and attributes from coordinator data."""
        status_info = self.coordinator.status_info()
        if status_info:
            _LOGGER.debug("Updating state from %s", status_info)
            self._attr_native_value = status_info.total
            self._attr_extra_state_attributes = {}
            for key, value in (
                (ATTR_STATUS, status_info.status),
                (
                    ATTR_LAST_UPDATE,
                    (
                        dt.as_utc(status_info.last_update)
                        if status_info.last_update
                        else None
                    ),
                ),
                (
                    ATTR_LAST_UPDATE_SUCCESSFUL,
                    (
                        dt.as_utc(status_info.last_update_successful)
                        if status_info.last_update_successful
                        else None
                    ),
                ),
                (ATTR_LAST_TIMESTAMP, status_info.last_timestamp),
                (ATTR_CREATED, status_info.created),
                (ATTR_UPDATED, status_info.updated),
                (ATTR_REMOVED, status_info.removed),
            ):
                if value or isinstance(value, bool):
                    self._attr_extra_state_attributes[key] = value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_internal_state()
        super()._handle_coordinator_update()
