"""Support for Speedtest.net internet speed testing sensor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.speedtestdotnet import SpeedTestDataCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_BYTES_RECEIVED,
    ATTR_BYTES_SENT,
    ATTR_SERVER_COUNTRY,
    ATTR_SERVER_ID,
    ATTR_SERVER_NAME,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    ICON,
    SENSOR_TYPES,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Speedtestdotnet sensors."""
    speedtest_coordinator = hass.data[DOMAIN]
    async_add_entities(
        SpeedtestSensor(speedtest_coordinator, sensor_type)
        for sensor_type in SENSOR_TYPES
    )


class SpeedtestSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Implementation of a speedtest.net sensor."""

    coordinator: SpeedTestDataCoordinator

    _attr_icon = ICON

    def __init__(self, coordinator: SpeedTestDataCoordinator, sensor_type: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.type = sensor_type

        self._attr_name = f"{DEFAULT_NAME} {SENSOR_TYPES[sensor_type][0]}"
        self._attr_unit_of_measurement = SENSOR_TYPES[self.type][1]
        self._attr_unique_id = sensor_type

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if not self.coordinator.data:
            return None

        attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_SERVER_NAME: self.coordinator.data["server"]["name"],
            ATTR_SERVER_COUNTRY: self.coordinator.data["server"]["country"],
            ATTR_SERVER_ID: self.coordinator.data["server"]["id"],
        }

        if self.type == "download":
            attributes[ATTR_BYTES_RECEIVED] = self.coordinator.data["bytes_received"]
        elif self.type == "upload":
            attributes[ATTR_BYTES_SENT] = self.coordinator.data["bytes_sent"]

        return attributes

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._attr_state = state.state

        @callback
        def update() -> None:
            """Update state."""
            self._update_state()
            self.async_write_ha_state()

        self.async_on_remove(self.coordinator.async_add_listener(update))
        self._update_state()

    def _update_state(self) -> None:
        """Update sensors state."""
        if not self.coordinator.data:
            return

        if self.type == "ping":
            self._attr_state = self.coordinator.data["ping"]
        elif self.type == "download":
            self._attr_state = round(self.coordinator.data["download"] / 10 ** 6, 2)
        elif self.type == "upload":
            self._attr_state = round(self.coordinator.data["upload"] / 10 ** 6, 2)
