"""Support for Speedtest.net internet speed testing sensor."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.speedtestdotnet import SpeedTestDataCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType
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
    SpeedtestSensorEntityDescription,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Speedtestdotnet sensors."""
    speedtest_coordinator = hass.data[DOMAIN]
    async_add_entities(
        SpeedtestSensor(speedtest_coordinator, description)
        for description in SENSOR_TYPES
    )


class SpeedtestSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Implementation of a speedtest.net sensor."""

    coordinator: SpeedTestDataCoordinator
    entity_description: SpeedtestSensorEntityDescription
    _attr_icon = ICON

    def __init__(
        self,
        coordinator: SpeedTestDataCoordinator,
        description: SpeedtestSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{DEFAULT_NAME} {description.name}"
        self._attr_unique_id = description.key
        self._state: StateType = None
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=DEFAULT_NAME,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.speedtest.net/",
        )

    @property
    def native_value(self) -> StateType:
        """Return native value for entity."""
        if self.coordinator.data:
            state = self.coordinator.data[self.entity_description.key]
            self._state = cast(StateType, self.entity_description.value(state))
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.coordinator.data:
            self._attrs.update(
                {
                    ATTR_SERVER_NAME: self.coordinator.data["server"]["name"],
                    ATTR_SERVER_COUNTRY: self.coordinator.data["server"]["country"],
                    ATTR_SERVER_ID: self.coordinator.data["server"]["id"],
                }
            )

            if self.entity_description.key == "download":
                self._attrs[ATTR_BYTES_RECEIVED] = self.coordinator.data[
                    ATTR_BYTES_RECEIVED
                ]
            elif self.entity_description.key == "upload":
                self._attrs[ATTR_BYTES_SENT] = self.coordinator.data[ATTR_BYTES_SENT]

        return self._attrs

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if state := await self.async_get_last_state():
            self._state = state.state
