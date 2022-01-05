"""Support for Launch Library sensors."""
from __future__ import annotations

from typing import Any

from pylaunches.objects.launch import Launch

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    ATTR_AGENCY,
    ATTR_AGENCY_COUNTRY_CODE,
    ATTR_LAUNCH_TIME,
    ATTR_STREAM,
    ATTRIBUTION,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    coordinator = hass.data[DOMAIN]

    async_add_entities(
        [
            NextLaunchSensor(coordinator, entry.entry_id),
        ]
    )


class LLBaseEntity(CoordinatorEntity, SensorEntity):
    """Sensor base entity."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize a Launch Library entity."""
        super().__init__(coordinator)

    def get_next_launch(self) -> Launch | None:
        """Return next launch."""
        return next((launch for launch in self.coordinator.data), None)


class NextLaunchSensor(LLBaseEntity):
    """Representation of the next launch sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:rocket-launch"
    _attr_name = "Next launch"

    def __init__(self, coordinator: DataUpdateCoordinator, entry_id: str) -> None:
        """Create Next launch sensor from base entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_next_launch"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        next_launch = self.get_next_launch()
        return next_launch.name if next_launch else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the attributes of the sensor."""
        if not (next_launch := self.get_next_launch()):
            return {}
        return {
            ATTR_LAUNCH_TIME: next_launch.net,
            ATTR_AGENCY: next_launch.launch_service_provider.name,
            ATTR_AGENCY_COUNTRY_CODE: next_launch.pad.location.country_code,
            ATTR_STREAM: next_launch.webcast_live,
        }
